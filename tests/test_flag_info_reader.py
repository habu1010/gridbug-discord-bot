"""FlagInfoReader のテスト

flag_info.txt はフラグ名 -> 日本語表示名 / 表示グループ の対応表。
実ファイルに対する回帰テストも兼ねる。
"""

import sqlite3

import pytest
from conftest import REAL_FLAG_INFO_PATH, fixture_path

from FlagInfoReader import FlagInfoReader


def collect_groups(path: str) -> list:
    return list(FlagInfoReader().get_flag_groups(path))


# ArtifactSpoiler.describe_artifact() が表示に使うグループ
USED_FLAG_GROUPS = [
    "BONUS",
    "SLAYING",
    "BRAND",
    "IMMUNITY",
    "RESISTANCE",
    "VULNERABILITY",
    "SUSTAIN_STATUS",
    "ESP",
    "POWER",
    "MISC",
    "CURSE",
    "XTRA",
]


class Test_get_flag_groups:
    def test_グループ単位でフラグを取得できる(self):
        groups = collect_groups(fixture_path("flag_info_sample.txt"))

        assert [g["name"] for g in groups] == ["BONUS", "POWER", "RESISTANCE"]
        assert groups[0]["description"] == "修正"
        assert groups[0]["flags"] == [
            {"name": "STR", "description": "腕力"},
            {"name": "DEX", "description": "器用"},
        ]

    def test_グループ説明が空でも読み込める(self):
        groups = {
            g["name"]: g
            for g in collect_groups(fixture_path("flag_info_sample.txt"))
        }

        assert groups["POWER"]["description"] == ""
        assert len(groups["POWER"]["flags"]) == 2

    def test_yieldされる辞書はグループ毎に独立している(self):
        # まとめて list() で受けても、後続のグループで上書きされないこと
        groups = list(
            FlagInfoReader().get_flag_groups(fixture_path("flag_info_sample.txt"))
        )

        assert [g["name"] for g in groups] == ["BONUS", "POWER", "RESISTANCE"]
        assert groups[0]["flags"][0] == {"name": "STR", "description": "腕力"}
        assert len({id(g) for g in groups}) == len(groups)

    def test_空行やコロンのない行は無視される(self, tmp_path):
        path = tmp_path / "flag_info.txt"
        path.write_text(
            "$GROUP_START:TEST:テスト\n"
            "\n"
            "コロンのない行\n"
            "A:あ\n"
            "B:い:余分なコロン\n"
            "$GROUP_END\n",
            encoding="utf-8",
        )

        groups = list(FlagInfoReader().get_flag_groups(str(path)))

        # "A:あ" だけが取り込まれる (コロンが2個の行は列数が合わず無視される)
        assert groups[0]["flags"] == [{"name": "A", "description": "あ"}]


class Test_create_flag_info_table:
    def test_グループ内の並び順がid_in_groupになる(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        FlagInfoReader().create_flag_info_table(
            db_path, fixture_path("flag_info_sample.txt")
        )

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = {
                r["name"]: dict(r)
                for r in conn.execute("SELECT * FROM flag_info").fetchall()
            }

        assert rows["STR"] == {
            "name": "STR",
            "flag_group": "BONUS",
            "id_in_group": 1,
            "description": "腕力",
        }
        assert rows["DEX"]["id_in_group"] == 2
        assert rows["RES_ACID"]["flag_group"] == "RESISTANCE"
        assert rows["RES_ACID"]["id_in_group"] == 1

    def test_再実行しても重複しない(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        reader = FlagInfoReader()
        reader.create_flag_info_table(db_path, fixture_path("flag_info_sample.txt"))
        reader.create_flag_info_table(db_path, fixture_path("flag_info_sample.txt"))

        with sqlite3.connect(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM flag_info").fetchone()[0]

        assert count == 6


class Test_実際のflag_info_txt:
    """リポジトリの flag_info.txt そのものに対する回帰テスト"""

    def test_フラグ名が重複していない(self):
        groups = collect_groups(REAL_FLAG_INFO_PATH)
        names = [flag["name"] for g in groups for flag in g["flags"]]

        assert len(names) == len(set(names))

    def test_表示に使うグループが全て定義されている(self, flag_info_db):
        with sqlite3.connect(flag_info_db) as conn:
            defined = {
                r[0] for r in conn.execute("SELECT DISTINCT flag_group FROM flag_info")
            }

        # POWER グループは現在フラグが空のため定義自体が存在しない
        assert set(USED_FLAG_GROUPS) - {"POWER"} <= defined

    def test_スレイは全てSLAYとKILLの対で定義されている(self, flag_info_db):
        # 本家でスレイ対象が追加されると SLAY_x と KILL_x が対で増えるため、
        # 片方だけ追加し忘れると検出される (コミット 1d689a1 は SLAY_GOOD /
        # KILL_GOOD の追加だった)
        slay, kill = self.slaying_flags(flag_info_db)

        assert set(slay) == set(kill)

    def test_KILLの説明はSLAYの説明を米印で囲んだもの(self, flag_info_db):
        slay, kill = self.slaying_flags(flag_info_db)

        assert kill == {target: f"*{desc}*" for target, desc in slay.items()}

    @pytest.mark.parametrize(
        ("group", "prefix"), [("IMMUNITY", "IM_"), ("VULNERABILITY", "VUL_")]
    )
    def test_免疫と弱点には対応する耐性が定義されている(self, flag_info_db, group, prefix):
        # 属性が追加された時に、耐性側か免疫/弱点側だけになるのを防ぐ
        elements = self.flag_targets(flag_info_db, group, prefix)
        resistances = self.flag_targets(flag_info_db, "RESISTANCE", "RES_")

        assert elements
        assert set(elements) <= set(resistances)

    @staticmethod
    def flag_targets(db_path: str, group: str, prefix: str) -> dict:
        """指定グループの、接頭辞を除いた対象名 -> 説明 の辞書を返す"""
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT name, description FROM flag_info WHERE flag_group = :group",
                {"group": group},
            ).fetchall()

        return {
            name[len(prefix) :]: description
            for name, description in rows
            if name.startswith(prefix)
        }

    def slaying_flags(self, db_path: str) -> tuple:
        """SLAYING グループの SLAY_ / KILL_ を対象名の辞書にして返す"""
        slay = self.flag_targets(db_path, "SLAYING", "SLAY_")
        kill = self.flag_targets(db_path, "SLAYING", "KILL_")

        assert slay and kill
        return slay, kill

    def test_スレイグループはSLAYとKILLだけで構成される(self, flag_info_db):
        with sqlite3.connect(flag_info_db) as conn:
            names = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM flag_info WHERE flag_group = 'SLAYING'"
                )
            ]

        assert names
        assert all(n.startswith(("SLAY_", "KILL_")) for n in names)

    def test_全てのフラグに説明が付いている(self, flag_info_db):
        with sqlite3.connect(flag_info_db) as conn:
            empty = conn.execute(
                "SELECT name FROM flag_info WHERE description = ''"
            ).fetchall()

        assert empty == []
