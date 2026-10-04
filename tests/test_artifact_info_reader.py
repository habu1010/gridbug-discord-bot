"""ArtifactInfoReader のテスト

本家の lib/edit/ArtifactDefinitions.jsonc からアーティファクト情報を読み取り、
tval/sval から導出した属性と共にSQLiteへ格納する。
"""

import logging
import sqlite3

import pytest
from conftest import REAL_FLAG_INFO_PATH

from ArtifactInfoReader import ArtifactInfoReader
from FlagInfoReader import FlagInfoReader

ArtifactInfo = ArtifactInfoReader.ArtifactInfo


class Test_is_complete_data:
    def test_idがなければ不完全(self):
        assert not ArtifactInfo().is_complete_data()
        assert ArtifactInfo(id=1).is_complete_data()


class Test_is_melee_weapon:
    @pytest.mark.parametrize(
        ("tval", "expected"),
        [(19, False), (20, True), (21, True), (23, True), (24, False)],
    )
    def test_tvalの境界(self, tval, expected):
        assert ArtifactInfo(tval=tval).is_melee_weapon is expected


class Test_range_weapon_mult:
    @pytest.mark.parametrize(
        ("sval", "expected"),
        [(2, 2), (12, 2), (13, 3), (23, 3), (24, 4), (63, 3)],
    )
    def test_svalごとの倍率(self, sval, expected):
        assert ArtifactInfo(tval=19, sval=sval).range_weapon_mult == expected

    def test_射撃武器以外は0(self):
        assert ArtifactInfo(tval=20, sval=13).range_weapon_mult == 0

    def test_未知のsvalは0(self):
        assert ArtifactInfo(tval=19, sval=99).range_weapon_mult == 0

    def test_XTRA_MIGHTで倍率が1増える(self):
        art = ArtifactInfo(tval=19, sval=13, flags=["XTRA_MIGHT"])

        assert art.range_weapon_mult == 4

    def test_XTRA_MIGHT以外のフラグでは増えない(self):
        art = ArtifactInfo(tval=19, sval=13, flags=["XTRA_SHOTS"])

        assert art.range_weapon_mult == 3


class Test_防具判定:
    @pytest.mark.parametrize(
        ("tval", "expected"),
        [(29, False), (30, True), (37, True), (38, True), (39, False)],
    )
    def test_is_protective_equipment(self, tval, expected):
        assert ArtifactInfo(tval=tval).is_protective_equipment is expected

    @pytest.mark.parametrize(
        ("tval", "expected"),
        [(35, False), (36, True), (37, True), (38, True), (39, False)],
    )
    def test_is_armor(self, tval, expected):
        assert ArtifactInfo(tval=tval).is_armor is expected


class Test_get_a_info_list:
    def test_全項目を読み取れる(self, artifact_defs_txt):
        reader = ArtifactInfoReader()
        arts = {a.id: a for a in reader.get_a_info_list(artifact_defs_txt)}
        art = arts[19]

        assert art.name == "『魂の守り手』"
        assert art.english_name == "'Soulkeeper'"
        assert art.tval == 37
        assert art.sval == 30
        assert art.pval == 2
        assert art.depth == 75
        assert art.rarity == 9
        assert art.weight == 420
        assert art.cost == 200000
        assert art.base_ac == 40
        assert art.base_dam == "2d4"
        assert art.to_hit == -4
        assert art.to_dam == 0
        assert art.to_ac == 20
        assert art.activate_flag == "CURE_1000"
        assert "HOLD_EXP" in art.flags

    def test_任意項目を省略すると既定値になる(self, artifact_defs_txt):
        reader = ArtifactInfoReader()
        arts = {a.id: a for a in reader.get_a_info_list(artifact_defs_txt)}
        art = arts[200]

        assert art.pval == 0
        assert art.base_ac == 0
        assert art.base_dam == ""
        assert art.to_hit == 0
        assert art.to_dam == 0
        assert art.to_ac == 0
        assert art.flags == []
        assert art.activate_flag == "NONE"

    def test_全件読み込まれる(self, artifact_defs_txt):
        arts = list(ArtifactInfoReader().get_a_info_list(artifact_defs_txt))

        assert [a.id for a in arts] == [1, 19, 96, 124, 200]


class Test_create_a_info_table:
    def test_a_infoに導出項目も含めて書き込まれる(self, art_db):
        with sqlite3.connect(art_db) as conn:
            conn.row_factory = sqlite3.Row
            rows = {
                r["id"]: dict(r)
                for r in conn.execute("SELECT * FROM a_info").fetchall()
            }

        assert len(rows) == 5

        # 近接武器 (グロンド)
        assert rows[96]["is_melee_weapon"] == 1
        assert rows[96]["range_weapon_mult"] == 0
        assert rows[96]["base_dam"] == "3d9"

        # 射撃武器 (XTRA_MIGHT 付きロング・ボウ)
        assert rows[124]["is_melee_weapon"] == 0
        assert rows[124]["range_weapon_mult"] == 4

        # 鎧
        assert rows[19]["is_protective_equipment"] == 1
        assert rows[19]["is_armor"] == 1

        # 光源 (防具でも武器でもない)
        assert rows[1]["is_melee_weapon"] == 0
        assert rows[1]["is_protective_equipment"] == 0
        assert rows[1]["is_armor"] == 0

    def test_a_info_flagsにフラグが展開される(self, art_db):
        with sqlite3.connect(art_db) as conn:
            flags = {
                r[0]
                for r in conn.execute("SELECT flag FROM a_info_flags WHERE id = 96")
            }

        assert flags == {
            "FULL_NAME",
            "SLAY_EVIL",
            "KILL_GOOD",
            "BRAND_FIRE",
            "ACTIVATE",
        }

    def test_フラグのないアーティファクトは行が作られない(self, art_db):
        with sqlite3.connect(art_db) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM a_info_flags WHERE id = 200"
            ).fetchone()[0]

        assert count == 0

    def test_インデックスが作られる(self, art_db):
        with sqlite3.connect(art_db) as conn:
            indexes = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index'"
                )
            ]

        assert "a_info_flags_index_id" in indexes

    def test_再実行しても重複しない(self, art_db, artifact_defs_txt):
        ArtifactInfoReader().create_a_info_table(art_db, artifact_defs_txt)

        with sqlite3.connect(art_db) as conn:
            a_count = conn.execute("SELECT COUNT(*) FROM a_info").fetchone()[0]
            f_count = conn.execute("SELECT COUNT(*) FROM a_info_flags").fetchone()[0]

        assert a_count == 5
        assert f_count == 16

    def test_create_a_info_tableは未知のフラグを警告しない(self, art_db, caplog):
        # 警告は flag_info の作成状況を知っている ArtifactSpoiler が
        # warn_unknown_flags() で行う
        a_info_txt = (
            '{"artifacts": [{"id": 999, "name": {"ja": "あ", "en": "a"},'
            ' "base_item": {"type_value": 40, "subtype_value": 10},'
            ' "level": 1, "rarity": 1, "weight": 1, "cost": 1,'
            ' "flags": ["NEW_UNKNOWN_FLAG"]}]}'
        )
        with caplog.at_level(logging.WARNING):
            ArtifactInfoReader().create_a_info_table(art_db, a_info_txt)

        assert "Unknown flag(s)" not in caplog.text


class Test_warn_unknown_flags:
    def test_flag_infoにないフラグは警告ログに出る(self, art_db, caplog):
        # 本家の spoiler-table.cpp にも flag_info.txt にも定義の無いフラグは
        # flag_info.txt への追加が必要なため、warning で通知している
        # (ChannelLogger経由でDiscordにも流れる)
        a_info_txt = """
{
    "artifacts": [
        {
            "id": 999,
            "name": { "ja": "未知の", "en": "of Unknown" },
            "base_item": { "type_value": 40, "subtype_value": 10 },
            "level": 1, "rarity": 1, "weight": 1, "cost": 1,
            "flags": ["STR", "NEW_UNKNOWN_FLAG"]
        }
    ]
}
"""
        reader = ArtifactInfoReader()
        reader.create_a_info_table(art_db, a_info_txt)
        with caplog.at_level(logging.WARNING):
            reader.warn_unknown_flags(art_db)

        assert "Unknown flag(s): NEW_UNKNOWN_FLAG" in caplog.text

    def test_本家の定義を取り込むまでは判定しない(
        self, tmp_path, artifact_defs_txt, caplog
    ):
        # flag_info.txt だけの flag_info では、本家テーブルにあるフラグ (CON など)
        # まで未知と判定してしまう
        db_path = str(tmp_path / "test.db")
        FlagInfoReader().create_flag_info_table(
            db_path, flag_info_path=REAL_FLAG_INFO_PATH
        )
        reader = ArtifactInfoReader()
        reader.create_a_info_table(db_path, artifact_defs_txt)

        with caplog.at_level(logging.INFO):
            reader.warn_unknown_flags(db_path)

        assert "Unknown flag(s)" not in caplog.text
        assert "未知のフラグの判定を保留します" in caplog.text

    def test_既知のフラグだけなら警告は出ない(self, art_db, artifact_defs_txt, caplog):
        reader = ArtifactInfoReader()
        reader.create_a_info_table(art_db, artifact_defs_txt)
        with caplog.at_level(logging.WARNING):
            reader.warn_unknown_flags(art_db)

        assert "Unknown flag(s)" not in caplog.text
