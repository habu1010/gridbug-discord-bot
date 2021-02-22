import re
import sqlite3
from typing import Iterator


class ActivationInfoReader():
    def get_activation_info_list(self, info_table_src: str) -> Iterator[dict]:
        pattern = re.compile(
            r'{\s*"(\w+)",\s*(\w+),\s*([-]?\d+)\s*,\s*([-]?\d+)\s*,'
            r'\s*{\s*([-]?\d+)\s*,\s*([-]?\d+)\s*},\s*_\("(.+)",\s*"(.+)"\)\s*}'
        )
        prev_line = None
        for line in info_table_src.splitlines():
            line = line.strip()
            m = pattern.match(prev_line + line) if prev_line else pattern.match(line)
            if m:
                yield {"flag": m[1], "level": int(m[3]), "value": int(m[4]), "timeout": int(m[5]), "dice": int(m[6]),
                       "desc": m[7], "eng_desc": m[8]}
                prev_line = None
            else:
                prev_line = line

        yield {"flag": "NONE", "level": 0, "value": 0, "timeout": 0, "dice": 0,
               "desc": "なし", "eng_desc": "none"}

    def create_activation_info_table(self, db_path: str, info_table_src: str) -> None:
        with sqlite3.connect(db_path) as conn:
            conn.execute("DROP TABLE IF EXISTS activation_info")
            conn.execute(
                '''
CREATE TABLE activation_info(
    flag TEXT PRIMARY KEY,
    level INTEGER,
    value INTEGER,
    timeout INTEGER,
    dice INTEGER,
    desc TEXT,
    eng_desc TEXT
)
''')
            conn.executemany(
                '''
INSERT INTO activation_info VALUES(:flag, :level, :value, :timeout, :dice, :desc, :eng_desc)
''',
                self.get_activation_info_list(info_table_src))
