import sqlite3
from dataclasses import asdict, dataclass
from typing import Iterator


class KindInfoReader:
    @dataclass
    class KindInfo:
        id: int = None
        name: str = ""
        english_name: str = ""
        tval: int = 0
        sval: int = 0
        pval: int = 0

        def is_complete_data(self):
            return self.id is not None

    def get_k_info_list(self, k_info_txt: str) -> Iterator[dict]:
        k_info = KindInfoReader.KindInfo()

        for line in k_info_txt.splitlines():
            cols = line.strip().split(":")
            if len(cols) <= 1:
                continue
            if cols[0] == "N":
                if k_info.is_complete_data():
                    yield asdict(k_info)
                    k_info = KindInfoReader.KindInfo()
                k_info.id = int(cols[1])
                k_info.name = cols[2]
            elif cols[0] == "E":
                k_info.english_name = cols[1]
            elif cols[0] == "I":
                k_info.tval = int(cols[1])
                k_info.sval = int(cols[2])
                k_info.pval = int(cols[3])

        if k_info.is_complete_data():
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
