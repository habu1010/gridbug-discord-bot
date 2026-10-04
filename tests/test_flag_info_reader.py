"""FlagInfoReader のテスト

flag_info テーブルは、本家 spoiler-table.cpp のフラグ定義を優先し、
そこに無いフラグを flag_info.txt で補って作る。
flag_info.txt の実ファイルに対する回帰テストも兼ねる。
"""

import logging
import sqlite3

import pytest
from conftest import REAL_FLAG_INFO_PATH, create_old_schema_flag_info, fixture_path

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
    "POWER",
    "MISC",
    "CURSE",
    "XTRA",
]


SAMPLE_FLAG_INFO_PATH = fixture_path("flag_info_sample.txt")


@pytest.fixture
def spoiler_flags(spoiler_table_src) -> dict[str, dict]:
    """縮小版 spoiler-table.cpp から取得したフラグ (フラグ名 -> エントリ、記述順)"""
    return {
        f["name"]: f
        for f in FlagInfoReader().get_spoiler_table_flags(spoiler_table_src)
    }


def read_flag_info(db_path: str) -> dict[str, dict]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return {
            r["name"]: dict(r)
            for r in conn.execute("SELECT * FROM flag_info").fetchall()
        }


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
            g["name"]: g for g in collect_groups(fixture_path("flag_info_sample.txt"))
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

    def test_空行やコメントやコロンのない行は無視される(self, tmp_path):
        path = tmp_path / "flag_info.txt"
        path.write_text(
            "# コメント: コロンを含んでもよい\n"
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


class Test_get_spoiler_table_flags:
    def test_テーブル名から表示グループが決まる(self, spoiler_flags):
        assert spoiler_flags["STR"] == {
            "name": "STR",
            "flag_group": "BONUS",
            "description": "腕力",
        }
        assert spoiler_flags["STEALTH"]["flag_group"] == "BONUS"
        assert spoiler_flags["KILL_GOOD"]["flag_group"] == "SLAYING"
        assert spoiler_flags["BRAND_FIRE"]["flag_group"] == "BRAND"
        assert spoiler_flags["RES_LITE"]["flag_group"] == "RESISTANCE"
        assert spoiler_flags["VUL_LITE"]["flag_group"] == "VULNERABILITY"
        assert spoiler_flags["IM_FIRE"]["flag_group"] == "IMMUNITY"
        assert spoiler_flags["SUST_CON"]["flag_group"] == "SUSTAIN_STATUS"
        assert spoiler_flags["HOLD_EXP"]["flag_group"] == "MISC"
        assert spoiler_flags["TELEPATHY"]["flag_group"] == "MISC"

    def test_記述順に取得できる(self, spoiler_flags):
        # 1行に複数エントリがあり "} };" で閉じるテーブルも読める
        assert list(spoiler_flags)[:6] == ["STR", "INT", "WIS", "DEX", "CON", "CHR"]

    def test_コメントアウトされたエントリは無視される(self, spoiler_flags):
        assert "XTRA_MIGHT" not in spoiler_flags
        assert "XTRA_SHOTS" not in spoiler_flags

    def test_フラグ以外のテーブルは無視される(self, spoiler_flags):
        descriptions = {f["description"] for f in spoiler_flags.values()}

        assert "刀剣" not in descriptions

    def test_未知のテーブルのフラグはMISCになる(self, spoiler_flags):
        assert spoiler_flags["NEW_TABLE_FLAG"]["flag_group"] == "MISC"

    def test_空文字列なら何も返さない(self):
        assert list(FlagInfoReader().get_spoiler_table_flags("")) == []


class Test_create_flag_info_table:
    def test_グループ内の並び順がid_in_groupになる(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        FlagInfoReader().create_flag_info_table(
            db_path, flag_info_path=SAMPLE_FLAG_INFO_PATH
        )

        rows = read_flag_info(db_path)

        assert rows["STR"] == {
            "name": "STR",
            "flag_group": "BONUS",
            "id_in_group": 1,
            "description": "腕力",
            "source": "flag_info.txt",
        }
        assert rows["DEX"]["id_in_group"] == 2
        assert rows["RES_ACID"]["flag_group"] == "RESISTANCE"
        assert rows["RES_ACID"]["id_in_group"] == 1

    def test_再実行しても重複しない(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        reader = FlagInfoReader()
        reader.create_flag_info_table(db_path, flag_info_path=SAMPLE_FLAG_INFO_PATH)
        reader.create_flag_info_table(db_path, flag_info_path=SAMPLE_FLAG_INFO_PATH)

        with sqlite3.connect(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM flag_info").fetchone()[0]

        assert count == 6

    def test_本家テーブルの名前とグループが優先される(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        FlagInfoReader().create_flag_info_table(
            db_path,
            """
const std::vector<flag_desc> stat_flags_desc = { { TR_DEX, _("器用さ", "DEX") } };
const std::vector<flag_desc> misc_flags2_desc = { { TR_FREE_ACT, _("麻痺", "FA") } };
""",
            SAMPLE_FLAG_INFO_PATH,
        )

        rows = read_flag_info(db_path)

        assert rows["DEX"]["description"] == "器用さ"
        assert rows["DEX"]["source"] == "spoiler-table.cpp"
        # flag_info.txt では POWER だが本家では MISC
        assert rows["FREE_ACT"]["flag_group"] == "MISC"
        assert rows["FREE_ACT"]["description"] == "麻痺"
        # 本家に無いフラグは flag_info.txt の定義が使われる
        assert rows["SEE_INVIS"]["flag_group"] == "POWER"
        assert rows["SEE_INVIS"]["description"] == "透明視認"
        assert rows["SEE_INVIS"]["source"] == "flag_info.txt"

    def test_flag_info_txtのフラグは本家のフラグの後に並ぶ(
        self, tmp_path, spoiler_table_src
    ):
        db_path = str(tmp_path / "test.db")
        FlagInfoReader().create_flag_info_table(
            db_path, spoiler_table_src, REAL_FLAG_INFO_PATH
        )

        rows = read_flag_info(db_path)
        misc = sorted(
            (r for r in rows.values() if r["flag_group"] == "MISC"),
            key=lambda r: r["id_in_group"],
        )
        names = [r["name"] for r in misc]

        # 本家の misc_flags2 -> misc_flags3 -> 未知テーブル -> flag_info.txt の順
        assert names[:2] == ["REFLECT", "HOLD_EXP"]
        assert names.index("NEW_TABLE_FLAG") < names.index("HARD_SPELL")
        assert names[-1] == "TELEPORT"
        assert [r["id_in_group"] for r in misc] == list(range(1, len(misc) + 1))

    def test_複数のテーブルにあるフラグは最初のものを採用する(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        FlagInfoReader().create_flag_info_table(
            db_path,
            """
const std::vector<flag_desc> resist_flags_desc = { { TR_X, _("耐性X", "X") } };
const std::vector<flag_desc> immune_flags_desc = { { TR_X, _("免疫X", "X") } };
""",
            SAMPLE_FLAG_INFO_PATH,
        )

        rows = read_flag_info(db_path)

        assert rows["X"]["flag_group"] == "RESISTANCE"
        assert rows["X"]["description"] == "耐性X"

    def test_本家テーブルから取得できなければ既存のテーブルを残す(
        self, tmp_path, caplog, spoiler_table_src
    ):
        db_path = str(tmp_path / "test.db")
        reader = FlagInfoReader()
        reader.create_flag_info_table(db_path, spoiler_table_src, SAMPLE_FLAG_INFO_PATH)
        before = read_flag_info(db_path)

        with caplog.at_level(logging.WARNING):
            reader.create_flag_info_table(
                db_path, "書式が変わった内容", SAMPLE_FLAG_INFO_PATH
            )

        assert "spoiler-table.cpp からフラグ定義を取得できませんでした" in caplog.text
        assert read_flag_info(db_path) == before

    def test_本家テーブルを渡さなければ警告しない(self, tmp_path, caplog):
        db_path = str(tmp_path / "test.db")
        with caplog.at_level(logging.WARNING):
            FlagInfoReader().create_flag_info_table(
                db_path, flag_info_path=SAMPLE_FLAG_INFO_PATH
            )

        assert caplog.text == ""


class Test_has_current_flag_info_table:
    def test_テーブルの有無を返す(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        reader = FlagInfoReader()

        assert not reader.has_current_flag_info_table(db_path)
        reader.create_flag_info_table(db_path, flag_info_path=SAMPLE_FLAG_INFO_PATH)
        assert reader.has_current_flag_info_table(db_path)

    def test_source列の無い古いテーブルは対象外(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        create_old_schema_flag_info(db_path)

        assert not FlagInfoReader().has_current_flag_info_table(db_path)


class Test_実際のflag_info_txt:
    """リポジトリの flag_info.txt そのものに対する回帰テスト"""

    def test_フラグ名が重複していない(self):
        groups = collect_groups(REAL_FLAG_INFO_PATH)
        names = [flag["name"] for g in groups for flag in g["flags"]]

        assert len(names) == len(set(names))

    def test_表示に使うグループかIGNOREだけを使っている(self):
        # グループ名を打ち間違えると、そのフラグは表示されなくなる
        groups = {g["name"] for g in collect_groups(REAL_FLAG_INFO_PATH)}

        assert groups <= set(USED_FLAG_GROUPS) | {"IGNORE"}

    def test_全てのフラグに説明が付いている(self):
        groups = collect_groups(REAL_FLAG_INFO_PATH)
        empty = [f["name"] for g in groups for f in g["flags"] if not f["description"]]

        assert empty == []
