import asyncio
import os
import sqlite3
from dataclasses import asdict, dataclass
from typing import List

import discord
from discord.ext import commands
from fuzzywuzzy import fuzz


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


class ArtifactSpoiler(commands.Cog):
    NUM_EMOJIS = [
        '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟'
    ]

    @dataclass
    class Artifact:
        """アーティファクト検索用クラス

        名前で検索する時に使用するクラス。
        IDとアーティファクト名だけ持ち、調べるアーティファクトが確定した後にIDでDBを検索する

        """
        id: int = 0
        fullname: str = ""

    def __init__(self, bot: commands.Command, config: dict):
        self.bot = bot
        self.db_path = os.path.expanduser(config["db_path"])
        k = KindInfoReader()
        k.create_k_info_table(self.db_path, os.path.expanduser(config["k_info_path"]))
        a = ArtifactInfoReader()
        a.create_a_info_table(self.db_path, os.path.expanduser(config["a_info_path"]))
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

        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.row_factory = sqlite3.Row
            c.execute(
                '''
SELECT
    a_info.id AS id,
    a_info.name AS a_name,
    k_info.name AS k_name,
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
                [self.Artifact(art["id"], fullname(art)) for art in c.fetchall()]
            pass

    @commands.command()
    async def art(self, ctx: commands.Context, name: str):
        candidates = [art for art in self.artifacts if name in art.fullname]
        if not candidates:
            suggests = sorted(
                self.artifacts,
                key=lambda x: fuzz.ratio(x.fullname, name), reverse=True
            )[:10]
            await self.choice_and_send_artifact_info(ctx, "もしかして:", suggests)
        elif len(candidates) == 1:
            await self.send_artifact_info(ctx, candidates[0])
        elif len(candidates) <= 10:
            await self.choice_and_send_artifact_info(ctx, "候補:", candidates)
        else:
            await self.send_error(ctx, "候補が多すぎます")

    async def send_artifact_info(self, ctx: commands.Context, art: Artifact):
        art_desc = self.describe_artifact(art)
        embed = discord.Embed(title=art_desc[0], description=art_desc[1])
        await ctx.reply(embed=embed)

    async def choice_and_send_artifact_info(self, ctx: commands.Context, choice_msg: str, candidates):
        msg = await self.send_artifact_candidates(ctx, choice_msg, candidates)
        choice = await self.wait_for_choice(ctx, msg)
        await msg.delete()
        if choice is not None:
            await self.send_artifact_info(ctx, candidates[choice])

    async def send_artifact_candidates(self, ctx: commands.Context, choice_msg: str, candidates):
        description = '\n'.join([num + " " + art.fullname for num, art in zip(self.NUM_EMOJIS, candidates)])
        embed = discord.Embed(title=choice_msg, description=description)
        msg: discord.Message = await ctx.reply(embed=embed)
        for i in range(len(candidates)):
            await msg.add_reaction(self.NUM_EMOJIS[i])
        return msg

    async def wait_for_choice(self, ctx: commands.Context, candidates_msg: discord.Message):
        def check(payload: discord.RawReactionActionEvent):
            return \
                ctx.message.author.id == payload.user_id and \
                payload.message_id == candidates_msg.id and \
                str(payload.emoji) in self.NUM_EMOJIS
        try:
            payload = await self.bot.wait_for('raw_reaction_add', timeout=15.0, check=check)
        except asyncio.TimeoutError:
            return None
        for i, emoji in enumerate(self.NUM_EMOJIS):
            if str(payload.emoji) == emoji:
                return i
        return None

    async def send_error(self, ctx: commands.Context, error_msg: str):
        embed = discord.Embed(title=error_msg, color=discord.Color.red())
        await ctx.reply(embed=embed)

    def describe_artifact(self, art: Artifact):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.row_factory = sqlite3.Row
            c.execute("SELECT * from a_info WHERE id = :id", {'id': art.id})
            a_info = c.fetchall()[0]
            c.execute(
                f'''
SELECT
    *
FROM
    a_info_flags
    JOIN flag_info ON a_info_flags.flag = flag_info.name
WHERE
    a_info_flags.id = {art.id}
ORDER BY
    flag_group,
    id_in_group
'''
            )
            flags = c.fetchall()

        main = f"[{art.id}] ★{art.fullname}"
        if a_info["is_melee_weapon"]:
            main += f" ({a_info['base_dam']})"
        elif a_info["range_weapon_mult"] > 0:
            main += f" (x{a_info['range_weapon_mult']})"
        main += self.describe_to_hit_dam(a_info)
        main += self.describe_ac(a_info)

        detail = self.describe_flag_group(flags, f"{a_info['pval']:+} ", 'BONUS')
        detail += self.describe_flag_group(flags, "スレイ: ", 'SLAYING')
        detail += self.describe_flag_group(flags, "属性: ", 'BRAND')
        detail += self.describe_flag_group(flags, "免疫: ", 'IMMUNITY')
        detail += self.describe_flag_group(flags, "耐性: ", 'RESISTANCE')
        detail += self.describe_flag_group(flags, "ESP: ", 'ESP')
        detail += self.describe_flag_group(flags, "維持: ", 'SUSTAIN')
        detail += self.describe_flag_group(flags, "", 'POWER')
        detail += self.describe_flag_group(flags, "", 'MISC')
        detail += self.describe_flag_group(flags, "", 'CURSE')
        detail += self.describe_flag_group(flags, "追加: ", 'XTRA')
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

    def output_test(self):
        for art in self.artifacts:
            print(self.describe_artifact(art))


def setup(bot):
    bot.add_cog(ArtifactSpoiler(bot, bot.ext))
