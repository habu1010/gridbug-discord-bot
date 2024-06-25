import sqlite3
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from Jsonc import parse_jsonc


class KindInfoReader:
    @dataclass
    class KindInfo:
        id: int | None = None
        name: str = ""
        english_name: str = ""
        tval: int = 0
        sval: int = 0
        pval: int = 0

        def is_complete_data(self):
            return self.id is not None

    def get_k_info_list(self, k_info_txt: str) -> Iterable[dict]:
        jsonc = parse_jsonc(k_info_txt)

        for baseitem in jsonc["baseitems"]:
            k_info = KindInfoReader.KindInfo()
            k_info.id = int(baseitem["id"])
            k_info.name = baseitem["name"]["ja"]
            k_info.english_name = baseitem["name"]["en"]
            k_info.tval = baseitem["itemkind"]["type_value"]
            k_info.sval = baseitem["itemkind"]["subtype_value"]
            k_info.pval = baseitem["parameter_value"]

            yield asdict(k_info)

    def create_k_info_table(self, db_path: str, k_info_txt: str) -> None:
        with sqlite3.connect(db_path) as conn:
            conn.execute("DROP TABLE IF EXISTS k_info")
            conn.execute(
                """
CREATE TABLE k_info(
    id INTEGER PRIMARY KEY,
    name TEXT,
    english_name TEXT,
    tval INTEGER,
    sval INTEGER,
    pval INTEGER
)
"""
            )
            conn.execute(
                """
CREATE INDEX k_info_index_tval_sval ON k_info(tval, sval)
"""
            )
            conn.executemany(
                """
INSERT INTO k_info values(:id, :name, :english_name, :tval, :sval, :pval)
""",
                self.get_k_info_list(k_info_txt),
            )
