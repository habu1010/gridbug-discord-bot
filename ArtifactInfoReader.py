import sqlite3
from dataclasses import asdict, dataclass
from typing import Iterator, List


class ArtifactInfoReader:
    @dataclass
    class ArtifactInfo:
        flags: List[str]
        id: int = None
        name: str = ""
        english_name: str = ""
        tval: int = 0
        sval: int = 0
        pval: int = 0
        depth: int = 0
        rarity: int = 0
        weight: int = 0
        cost: int = 0
        base_ac: int = 0
        base_dam: str = ""
        to_hit: int = 0
        to_dam: int = 0
        to_ac: int = 0
        activate_flag: str = "NONE"

        def __init__(self):
            self.flags = []

        def is_complete_data(self) -> bool:
            return self.id is not None

        @property
        def is_melee_weapon(self) -> bool:
            return 20 <= self.tval and self.tval <= 23

        @property
        def range_weapon_mult(self) -> int:
            if self.tval != 19:
                return 0
            mult = self.sval % 10  # svalの下1桁を基礎倍率とする仕様
            if "XTRA_MIGHT" in self.flags:
                mult += 1
            return mult

        @property
        def is_protective_equipment(self) -> bool:
            return 30 <= self.tval and self.tval <= 38

        @property
        def is_armor(self) -> bool:
            return 36 <= self.tval and self.tval <= 38

    def get_a_info_list(self, a_info_txt: str) -> Iterator[ArtifactInfo]:
        a_info = ArtifactInfoReader.ArtifactInfo()

        for line in a_info_txt.splitlines():
            cols = [col.strip() for col in line.split(":")]
            if len(cols) <= 1:
                continue
            if cols[0] == "N":
                if a_info.is_complete_data():
                    yield a_info
                    a_info = ArtifactInfoReader.ArtifactInfo()
                a_info.id = int(cols[1])
                a_info.name = cols[2]
            elif cols[0] == "E":
                a_info.english_name = cols[1]
            elif cols[0] == "I":
                a_info.tval = int(cols[1])
                a_info.sval = int(cols[2])
                a_info.pval = int(cols[3])
            elif cols[0] == "W":
                a_info.depth = int(cols[1])
                a_info.rarity = int(cols[2])
                a_info.weight = int(cols[3])
                a_info.cost = int(cols[4])
            elif cols[0] == "P":
                a_info.base_ac = int(cols[1])
                a_info.base_dam = cols[2]
                a_info.to_hit = int(cols[3])
                a_info.to_dam = int(cols[4])
                a_info.to_ac = int(cols[5])
            elif cols[0] == "F":
                flags = [flag.strip() for flag in cols[1].split('|') if flag.strip()]
                a_info.flags.extend(flags)
            elif cols[0] == "U":
                a_info.activate_flag = cols[1]

        if a_info.is_complete_data():
            yield a_info

    def create_a_info_table(self, db_path: str, a_info_txt: str) -> None:
        with sqlite3.connect(db_path) as conn:
            conn.execute("DROP TABLE IF EXISTS a_info")
            conn.execute("DROP TABLE IF EXISTS a_info_flags")
            a_info_list = tuple(self.get_a_info_list(a_info_txt))
            conn.execute(
                '''
CREATE TABLE a_info(
    id INTEGER PRIMARY KEY,
    name TEXT,
    english_name TEXT,
    tval INTEGER,
    sval INTEGER,
    pval INTEGER,
    depth INTEGER,
    rarity INGEGER,
    weight INGEGER,
    cost INGEGER,
    base_ac INGEGER,
    base_dam TEXT,
    to_hit INGEGER,
    to_dam INGEGER,
    to_ac INGEGER,
    activate_flag TEXT,
    is_melee_weapon BOOLEAN,
    range_weapon_mult INTEGER,
    is_protective_equipment BOOLEAN,
    is_armor BOOLEAN
)
'''
            )
            conn.execute(
                '''
CREATE TABLE a_info_flags(
    id INTEGER,
    flag TEXT
)
'''
            )
            for a_info in a_info_list:
                n = (a_info.is_melee_weapon,
                     a_info.range_weapon_mult,
                     a_info.is_protective_equipment,
                     a_info.is_armor)
                conn.execute(
                    f'''
INSERT INTO a_info values(
    :id, :name, :english_name, :tval, :sval, :pval,
    :depth, :rarity, :weight, :cost,
    :base_ac, :base_dam, :to_hit, :to_dam, :to_ac,
    :activate_flag,
    {a_info.is_melee_weapon}, {a_info.range_weapon_mult}, {a_info.is_protective_equipment}, {a_info.is_armor}
)
'''
                    .format(n),
                    asdict(a_info)
                )
            for a_info in a_info_list:
                for flag in a_info.flags:
                    conn.execute(
                        '''
INSERT INTO a_info_flags values(:id, :flag)
''',
                        {'id': a_info.id, 'flag': flag}
                    )
