import os
import re
import sqlite3
from dataclasses import asdict, dataclass
from typing import Iterator, List, Optional

import discord
from discord.ext import commands

import ListSearch
from ErrorCatchingArgumentParser import ErrorCatchingArgumentParser


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


class KindInfoReader:
    def get_k_info_list(self, k_info_path: str):
        k_info = KindInfo()
        with open(k_info_path) as f:
            lines = f.readlines()

        for line in lines:
            cols = line.strip().split(":")
            if len(cols) <= 1:
                continue
            if cols[0] == "N":
                if k_info.is_complete_data():
                    yield asdict(k_info)
                    k_info = KindInfo()
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

    def create_k_info_table(self, db_path: str, k_info_path: str):
        with sqlite3.connect(db_path) as conn:
            conn.execute("DROP TABLE IF EXISTS k_info")
            conn.execute(
                '''
CREATE TABLE k_info(
    id INTEGER PRIMARY KEY,
    name TEXT,
    english_name TEXT,
    tval INTEGER,
    sval INTEGER,
    pval INTEGER
)
'''
            )
            conn.executemany(
                '''
INSERT INTO k_info values(:id, :name, :english_name, :tval, :sval, :pval)
''',
                self.get_k_info_list(k_info_path))


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

    def is_complete_data(self):
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
    def is_protective_equipment(self):
        return 30 <= self.tval and self.tval <= 38

    @property
    def is_armor(self):
        return 36 <= self.tval and self.tval <= 38


class ArtifactInfoReader:
    def get_a_info_list(self, a_info_path: str):
        a_info = ArtifactInfo()
        with open(a_info_path) as f:
            lines = f.readlines()

        for line in lines:
            cols = [col.strip() for col in line.split(":")]
            if len(cols) <= 1:
                continue
            if cols[0] == "N":
                if a_info.is_complete_data():
                    yield a_info
                    a_info = ArtifactInfo()
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

    def create_a_info_table(self, db_path: str, a_info_path: str):
        with sqlite3.connect(db_path) as conn:
            conn.execute("DROP TABLE IF EXISTS a_info")
            conn.execute("DROP TABLE IF EXISTS a_info_flags")
            a_info_list = tuple(self.get_a_info_list(a_info_path))
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
        {a_info.is_melee_weapon}, {a_info.range_weapon_mult}, {a_info.is_protective_equipment}, { a_info.is_armor}
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


class FlagInfoReader:
    def get_flag_groups(self, flag_info_path: str):
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

    def create_flag_info_table(self, db_path: str, flag_info_path: str):
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


class ActivationInfoReader():
    def get_activation_info_list(self, info_table_file: str) -> Iterator[dict]:
        with open(info_table_file) as f:
            lines = [line.strip() for line in f.readlines()]

        pattern = re.compile(
            r'{\s*"(\w+)",\s*(\w+),\s*([-]?\d+)\s*,\s*([-]?\d+)\s*,'
            r'\s*{\s*([-]?\d+)\s*,\s*([-]?\d+)\s*},\s*_\("(.+)",\s*"(.+)"\)\s*}'
        )
        prev_line = None
        for line in lines:
            m = pattern.match(prev_line + line) if prev_line else pattern.match(line)
            if m:
                yield {"flag": m[1], "level": int(m[3]), "value": int(m[4]), "timeout": int(m[5]), "dice": int(m[6]),
                       "desc": m[7], "eng_desc": m[8]}
                prev_line = None
            else:
                prev_line = line

        yield {"flag": "NONE", "level": 0, "value": 0, "timeout": 0, "dice": 0,
               "desc": "なし", "eng_desc": "none"}

    def create_activation_info_table(self, db_path: str, info_table_file: str) -> None:
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
                self.get_activation_info_list(info_table_file))


class ArtifactSpoiler(commands.Cog):
    @dataclass
    class Artifact:
        """アーティファクト検索用クラス

        名前で検索する時に使用するクラス。
        IDとアーティファクト名だけ持ち、調べるアーティファクトが確定した後にIDでDBを検索する

        """
        id: int = 0
        fullname: str = ""
        fullname_en: str = ""

    def __init__(self, bot: commands.Command, config: dict):
        self.bot = bot
        self.db_path = os.path.expanduser(config["db_path"])
        hengband_dir = os.path.expanduser(config["hengband_dir"])
        k = KindInfoReader()
        k.create_k_info_table(self.db_path, os.path.join(hengband_dir, "lib/edit/k_info.txt"))
        a = ArtifactInfoReader()
        a.create_a_info_table(self.db_path, os.path.join(hengband_dir, "lib/edit/a_info.txt"))
        ai = ActivationInfoReader()
        ai.create_activation_info_table(self.db_path, os.path.join(
            hengband_dir, "src/object-enchant/activation-info-table.c"))
        f = FlagInfoReader()
        f.create_flag_info_table(
            self.db_path,
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "flag_info.txt"))

        def fullname(art: dict):
            a = art["a_name"]
            k = art["k_name"]
            if art["is_fullname"]:
                return a
            elif a.startswith("『"):
                return k + a
            return a + k

        def fullname_en(art: dict):
            a = art["a_name_en"]
            k = art["k_name_en"]
            f = a if art["is_fullname"] else f"{k} {a}"
            return f.replace("&", "The").replace("~", "")

        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.row_factory = sqlite3.Row
            c.execute(
                '''
SELECT
    a_info.id AS id,
    a_info.name AS a_name,
    a_info.english_name AS a_name_en,
    k_info.name AS k_name,
    k_info.english_name AS k_name_en,
    (
        SELECT
            COUNT(*)
        FROM
            a_info_flags
        WHERE
            a_info_flags.id = a_info.id
            AND a_info_flags.flag = 'FULL_NAME'
    ) AS is_fullname
FROM
    a_info
    JOIN k_info ON a_info.tval = k_info.tval
    AND a_info.sval = k_info.sval
'''
            )

            self.artifacts = \
                [asdict(self.Artifact(art["id"], fullname(art), fullname_en(art))) for art in c.fetchall()]
            pass

        self.parser = ErrorCatchingArgumentParser(prog="art", add_help=False)
        self.parser.add_argument("-e", "--english", action="store_true")
        self.parser.add_argument("artifact_name")

    @commands.command(usage="[-e] artifact_name")
    async def art(self, ctx: commands.Context, *args):
        """アーティファクトを検索する

        アーティファクトを名称の一部で検索し、情報を表示します。
        複数のアーティファクトが見つかった場合は候補を表示し、リアクションで選択します。
        一件もヒットしなかった場合は、あいまい検索により候補を表示します。

        positional arguments:
          artifact_name         検索するアーティファクトの名称の一部

        optional arguments:
          -e, --english         英語名で検索する
        """

        try:
            parse_result = self.parser.parse_args(args)
        except Exception:
            await ctx.send_help(ctx.command)
            return

        choice, error_msg = await ListSearch.search(
            ctx, self.artifacts, parse_result.artifact_name, "fullname", "fullname_en", parse_result.english)

        if choice:
            await self.send_artifact_info(ctx, choice)
        elif error_msg:
            await self.send_error(ctx, error_msg)

    async def send_artifact_info(self, ctx: commands.Context, art: Artifact):
        art_desc = self.describe_artifact(art)
        embed = discord.Embed(
            title=discord.utils.escape_markdown(art_desc[0]),
            description=discord.utils.escape_markdown(art_desc[1]))
        await ctx.reply(embed=embed)

    async def send_error(self, ctx: commands.Context, error_msg: str):
        embed = discord.Embed(title=error_msg, color=discord.Color.red())
        await ctx.reply(embed=embed)

    def describe_artifact(self, art: Artifact):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.row_factory = sqlite3.Row
            c.execute(
                '''
SELECT
    *
FROM
    a_info
    JOIN activation_info ON a_info.activate_flag = activation_info.flag
WHERE
    a_info.id = :id
''',
                {'id': art["id"]})
            a_info = c.fetchall()[0]
            c.execute(
                f'''
SELECT
    *
FROM
    a_info_flags
    JOIN flag_info ON a_info_flags.flag = flag_info.name
WHERE
    a_info_flags.id = {art['id']}
ORDER BY
    flag_group,
    id_in_group
'''
            )
            flags = c.fetchall()

        main = f"[{art['id']}] ★{art['fullname']}"
        if a_info["is_melee_weapon"]:
            main += f" ({a_info['base_dam']})"
        elif a_info["range_weapon_mult"] > 0:
            main += f" (x{a_info['range_weapon_mult']})"
        main += self.describe_to_hit_dam(a_info)
        main += self.describe_ac(a_info)

        main += f" / {art['fullname_en']}"

        detail = self.describe_flag_group(flags, f"{a_info['pval']:+} ", 'BONUS')
        detail += self.describe_flag_group(flags, "スレイ: ", 'SLAYING')
        detail += self.describe_flag_group(flags, "属性: ", 'BRAND')
        detail += self.describe_flag_group(flags, "免疫: ", 'IMMUNITY')
        detail += self.describe_flag_group(flags, "耐性: ", 'RESISTANCE')
        detail += self.describe_flag_group(flags, "ESP: ", 'ESP')
        detail += self.describe_flag_group(flags, "能力維持: ", 'SUSTAIN_STATUS')
        detail += self.describe_flag_group(flags, "", 'POWER')
        detail += self.describe_flag_group(flags, "", 'MISC')
        detail += self.describe_flag_group(flags, "", 'CURSE')
        detail += self.describe_flag_group(flags, "追加: ", 'XTRA')
        detail += self.describe_activation(a_info)
        detail += "\n\n"
        detail += f"階層:{a_info['depth']}, 希少度:{a_info['rarity']}, {a_info['weight']/20:.1f}kg, ${a_info['cost']}"

        return (main, detail)

    def describe_to_hit_dam(self, a_info: dict):
        to_hit = a_info["to_hit"]
        to_dam = a_info["to_dam"]
        res = ""
        if a_info["is_melee_weapon"] or to_hit != 0 or to_dam != 0:
            if a_info["is_armor"] and to_dam == 0:
                # 鎧でダメージ修正が無い物は命中修正しか表示しない
                res += f" ({to_hit:+})"
            else:
                res += f" ({to_hit:+},{to_dam:+})"
        return res

    def describe_ac(self, a_info: dict):
        res = ""
        if a_info["is_protective_equipment"] or a_info["base_ac"] > 0:
            res += f" [{a_info['base_ac']},{a_info['to_ac']:+}]"
        elif a_info["to_ac"] != 0:
            res += f" [{a_info['to_ac']:+}]"
        return res

    def describe_flag_group(self, flags, head: str, group_name: str):
        if group_name not in [flag["flag_group"] for flag in flags]:
            return ""
        return f"{head}" + ", ".join(
            [flag["description"] for flag in flags
             if flag["flag_group"] == group_name]
        )+"; "

    def describe_activation(self, a_info: dict):
        if a_info["activate_flag"] == "NONE":
            return ""
        timeout = (
            self.describe_activation_timeout(a_info['timeout'], a_info['dice']) or
            self.describe_activation_timeout_special(a_info['activate_flag'])
        )
        return f"\n発動した時の効果...\n{a_info['desc']} : {timeout}"

    def describe_activation_timeout(self, timeout, dice) -> Optional[str]:
        if timeout == 0:
            return "いつでも"
        elif timeout > 0 and dice == 0:
            return f"{timeout} ターン毎"
        elif timeout > 0 and dice > 0:
            return f"{timeout}+d{dice} ターン毎"

        return None

    def describe_activation_timeout_special(self, flag: str):
        DICT = {"TERROR": "3*(レベル+10) ターン毎",
                "MURAMASA": "確率50%で壊れる"}
        return DICT.get(flag, "不明")

    def output_test(self):
        for art in self.artifacts:
            print(self.describe_artifact(art))


def setup(bot):
    bot.add_cog(ArtifactSpoiler(bot, bot.ext))
