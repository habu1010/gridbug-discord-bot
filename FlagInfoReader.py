import sqlite3
from typing import Iterator


class FlagInfoReader:
    def get_flag_groups(self, flag_info_path: str) -> Iterator[dict]:
        with open(flag_info_path) as f:
            lines = [line.strip() for line in f.readlines()]

        flag_group = dict()
        for line in lines:
            if line.startswith("$GROUP_START"):
                cols = line.split(":")
                flag_group["name"] = cols[1]
                flag_group["description"] = cols[2]
                flag_group["flags"] = []
            elif line.startswith("$GROUP_END"):
                yield flag_group
            else:
                cols = line.split(":")
                if len(cols) == 2:
                    flag_group["flags"].append({"name": cols[0], "description": cols[1]})

    def create_flag_info_table(self, db_path: str, flag_info_path: str) -> None:
        with sqlite3.connect(db_path) as conn:
            conn.execute("DROP TABLE IF EXISTS flag_info")
            conn.execute(
                '''
CREATE TABLE flag_info(
    name TEXT PRIMARY KEY,
    flag_group TEXT,
    id_in_group INTEGER,
    description TEXT
)
'''
            )
            for flag_group in self.get_flag_groups(flag_info_path):
                for i, flag in enumerate(flag_group["flags"]):
                    conn.execute(
                        '''
INSERT INTO flag_info VALUES(:name, :flag_group, :id_in_group, :description)
''',
                        {"name": flag["name"], "flag_group": flag_group["name"],
                         "id_in_group": i+1, "description": flag["description"]}
                    )
