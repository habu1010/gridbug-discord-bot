"""ActivationInfoReader のテスト

本家の src/object-enchant/activation-info-table.cpp から
発動効果の定義を正規表現で抜き出す。
"""

import sqlite3

from ActivationInfoReader import ActivationInfoReader, convert_timeout_to_int


def parse(src: str) -> dict:
    """フラグ名をキーにした辞書を返す"""
    return {i["flag"]: i for i in ActivationInfoReader().get_activation_info_list(src)}


class Test_convert_timeout_to_int:
    def test_数値はそのまま整数になる(self):
        assert convert_timeout_to_int("100") == 100
        assert convert_timeout_to_int("0") == 0

    def test_数値でない場合は_1になる(self):
        # ACTIVATION_TERROR のような列挙子で書かれている場合
        assert convert_timeout_to_int("ACTIVATION_TERROR") == -1
        assert convert_timeout_to_int("") == -1


class Test_get_activation_info_list:
    def test_1行の定義をパースできる(self, activation_table_src):
        info = parse(activation_table_src)["SUNLIGHT"]

        assert info == {
            "flag": "SUNLIGHT",
            "level": 10,
            "value": 250,
            "timeout": 10,
            "dice": 0,
            "desc": "太陽光線",
            "eng_desc": "beam of sunlight",
        }

    def test_2行に折り返された定義をパースできる(self, activation_table_src):
        # 前の行を保持して結合してからマッチさせている
        info = parse(activation_table_src)["BR_FIRE"]

        assert info["level"] == 40
        assert info["value"] == 1000
        assert info["timeout"] == 250
        assert info["desc"] == "火炎のブレス (200)"
        assert info["eng_desc"] == "breathe fire (200)"

    def test_タイムアウトが列挙子の場合は_1になる(self, activation_table_src):
        infos = parse(activation_table_src)

        assert infos["TERROR"]["timeout"] == -1
        assert infos["MURAMASA"]["timeout"] == -1

    def test_ダイス付きのタイムアウトを取得できる(self, activation_table_src):
        info = parse(activation_table_src)["LIGHT"]

        assert info["timeout"] == 10
        assert info["dice"] == 10

    def test_タイムアウト0の定義を取得できる(self, activation_table_src):
        info = parse(activation_table_src)["BERSERK"]

        assert info["timeout"] == 0
        assert info["dice"] == 0

    def test_末尾に必ずNONEが追加される(self, activation_table_src):
        infos = list(
            ActivationInfoReader().get_activation_info_list(activation_table_src)
        )

        assert infos[-1] == {
            "flag": "NONE",
            "level": 0,
            "value": 0,
            "timeout": 0,
            "dice": 0,
            "desc": "なし",
            "eng_desc": "none",
        }

    def test_定義行以外は無視される(self, activation_table_src):
        infos = parse(activation_table_src)

        # #include やコメント、vector の宣言行が混ざらないこと
        assert set(infos) == {
            "SUNLIGHT",
            "LIGHT",
            "CURE_1000",
            "TERROR",
            "MURAMASA",
            "BERSERK",
            "BR_FIRE",
            "DISP_EVIL",
            "NONE",
        }

    def test_定義が無くてもNONEだけは返る(self):
        assert list(ActivationInfoReader().get_activation_info_list("")) == [
            {
                "flag": "NONE",
                "level": 0,
                "value": 0,
                "timeout": 0,
                "dice": 0,
                "desc": "なし",
                "eng_desc": "none",
            }
        ]


class Test_create_activation_info_table:
    def test_テーブルに書き込まれる(self, tmp_path, activation_table_src):
        db_path = str(tmp_path / "test.db")
        ActivationInfoReader().create_activation_info_table(
            db_path, activation_table_src
        )

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = {
                r["flag"]: dict(r)
                for r in conn.execute("SELECT * FROM activation_info").fetchall()
            }

        assert len(rows) == 9
        assert rows["CURE_1000"]["desc"] == "*体力回復*"
        assert rows["CURE_1000"]["timeout"] == 888
        assert rows["NONE"]["desc"] == "なし"

    def test_再実行しても重複しない(self, tmp_path, activation_table_src):
        db_path = str(tmp_path / "test.db")
        reader = ActivationInfoReader()
        reader.create_activation_info_table(db_path, activation_table_src)
        reader.create_activation_info_table(db_path, activation_table_src)

        with sqlite3.connect(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM activation_info").fetchone()[0]

        assert count == 9
