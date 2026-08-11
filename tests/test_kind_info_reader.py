"""KindInfoReader のテスト

本家の lib/edit/BaseitemDefinitions.jsonc からベースアイテム情報を読み取る。
"""

import sqlite3

from KindInfoReader import KindInfoReader


class Test_get_k_info_list:
    def test_jsoncから辞書のリストに変換できる(self, baseitem_defs_txt):
        reader = KindInfoReader()
        items = {i["id"]: i for i in reader.get_k_info_list(baseitem_defs_txt)}

        assert items[501] == {
            "id": 501,
            "name": "の燦光",
            "english_name": "& Phial~",
            "tval": 39,
            "sval": 4,
            "pval": 0,
        }
        assert len(items) == 5

    def test_idは整数に変換される(self, baseitem_defs_txt):
        items = list(KindInfoReader().get_k_info_list(baseitem_defs_txt))

        assert all(isinstance(i["id"], int) for i in items)


class Test_create_k_info_table:
    def test_テーブルに書き込まれる(self, tmp_path, baseitem_defs_txt):
        db_path = str(tmp_path / "test.db")
        KindInfoReader().create_k_info_table(db_path, baseitem_defs_txt)

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM k_info ORDER BY id").fetchall()

        assert len(rows) == 5
        assert dict(rows[0]) == {
            "id": 501,
            "name": "の燦光",
            "english_name": "& Phial~",
            "tval": 39,
            "sval": 4,
            "pval": 0,
        }

    def test_tvalとsvalの複合インデックスが作られる(self, tmp_path, baseitem_defs_txt):
        # a_info との JOIN に使われるインデックス
        db_path = str(tmp_path / "test.db")
        KindInfoReader().create_k_info_table(db_path, baseitem_defs_txt)

        with sqlite3.connect(db_path) as conn:
            indexes = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index'"
                )
            ]

        assert "k_info_index_tval_sval" in indexes

    def test_再実行してもテーブルが作り直される(self, tmp_path, baseitem_defs_txt):
        db_path = str(tmp_path / "test.db")
        reader = KindInfoReader()
        reader.create_k_info_table(db_path, baseitem_defs_txt)
        reader.create_k_info_table(db_path, baseitem_defs_txt)

        with sqlite3.connect(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM k_info").fetchone()[0]

        assert count == 5
