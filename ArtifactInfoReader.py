import sqlite3
from dataclasses import asdict, dataclass, field
from logging import getLogger
from typing import Iterator

from Jsonc import parse_jsonc


class ArtifactInfoReader:
    @dataclass
    class ArtifactInfo:
        flags: list[str] = field(default_factory=list)
        id: int | None = None
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

        def is_complete_data(self) -> bool:
            return self.id is not None

        @property
        def is_melee_weapon(self) -> bool:
            return 20 <= self.tval and self.tval <= 23

        @property
        def range_weapon_mult(self) -> int:
            if self.tval != 19:
                return 0

            sval_to_mult = {
                2: 2,  # スリング
                12: 2,  # ショート・ボウ
                13: 3,  # ロング・ボウ
                23: 3,  # ライト・クロスボウ
                24: 4,  # ヘヴィ・クロスボウ
                63: 3,  # いいかげんな弓
            }
            mult = sval_to_mult.get(self.sval, 0)

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
        jsonc = parse_jsonc(a_info_txt)

        for artifact in jsonc["artifacts"]:
            a_info = ArtifactInfoReader.ArtifactInfo()
            a_info.id = artifact["id"]
            a_info.name = artifact["name"]["ja"]
            a_info.english_name = artifact["name"]["en"]
            a_info.tval = artifact["base_item"]["type_value"]
            a_info.sval = artifact["base_item"]["subtype_value"]
            a_info.pval = artifact.get("parameter_value", 0)
            a_info.depth = artifact["level"]
            a_info.rarity = artifact["rarity"]
            a_info.weight = artifact["weight"]
            a_info.cost = artifact["cost"]
            a_info.base_ac = artifact.get("base_ac", 0)
            a_info.base_dam = artifact.get("base_dice", "")
            a_info.to_hit = artifact.get("hit_bonus", 0)
            a_info.to_dam = artifact.get("damage_bonus", 0)
            a_info.to_ac = artifact.get("ac_bonus", 0)
            a_info.flags = artifact.get("flags", [])
            a_info.activate_flag = artifact.get("activate", "NONE")

            yield a_info

    def create_a_info_table(self, db_path: str, a_info_txt: str) -> None:
        with sqlite3.connect(db_path) as conn:
            conn.execute("DROP TABLE IF EXISTS a_info")
            conn.execute("DROP TABLE IF EXISTS a_info_flags")
            conn.execute(
                """
CREATE TABLE a_info(
    id INTEGER PRIMARY KEY,
    name TEXT,
    english_name TEXT,
    tval INTEGER,
    sval INTEGER,
    pval INTEGER,
    depth INTEGER,
    rarity INTEGER,
    weight INTEGER,
    cost INTEGER,
    base_ac INTEGER,
    base_dam TEXT,
    to_hit INTEGER,
    to_dam INTEGER,
    to_ac INTEGER,
    activate_flag TEXT,
    is_melee_weapon BOOLEAN,
    range_weapon_mult INTEGER,
    is_protective_equipment BOOLEAN,
    is_armor BOOLEAN
)
"""
            )
            conn.execute(
                """
CREATE TABLE a_info_flags(
    id INTEGER,
    flag TEXT
)
"""
            )
            conn.execute(
                """
CREATE INDEX a_info_flags_index_id ON a_info_flags(id)
"""
            )

            a_info_flags = set()

            for a_info in self.get_a_info_list(a_info_txt):
                a_info_flags.update(a_info.flags)
                conn.execute(
                    f"""
INSERT INTO a_info values(
    :id, :name, :english_name, :tval, :sval, :pval,
    :depth, :rarity, :weight, :cost,
    :base_ac, :base_dam, :to_hit, :to_dam, :to_ac,
    :activate_flag,
    {a_info.is_melee_weapon},
    {a_info.range_weapon_mult},
    {a_info.is_protective_equipment},
    {a_info.is_armor}
)
""",
                    asdict(a_info),
                )

                for flag in a_info.flags:
                    conn.execute(
                        """
INSERT INTO a_info_flags values(:id, :flag)
""",
                        {"id": a_info.id, "flag": flag},
                    )

            # flag_info.txt に登録されていないフラグのチェック
            known_flags = {
                row[0] for row in conn.execute("SELECT name FROM flag_info").fetchall()
            }
            if unknown_flags := a_info_flags - known_flags:
                unknown_flags_str = ",".join(unknown_flags)
                getLogger(__name__).warning(f"Unknown flag(s): {unknown_flags_str}")
