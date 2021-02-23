import asyncio
import os
from dataclasses import asdict, dataclass
from typing import Optional

import aiohttp
import aiosqlite
import discord
from discord.ext import commands, tasks

import ActivationInfoReader
import ArtifactInfoReader
import FlagInfoReader
import KindInfoReader
import ListSearch
from ErrorCatchingArgumentParser import ErrorCatchingArgumentParser


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
        self.hengband_src_url = config["hengband_src_url"]
        self.client_session = aiohttp.ClientSession()
        self.etags = {}

        f = FlagInfoReader.FlagInfoReader()
        f.create_flag_info_table(
            self.db_path,
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "flag_info.txt"))

        self.parser = ErrorCatchingArgumentParser(prog="art", add_help=False)
        self.parser.add_argument("-e", "--english", action="store_true")
        self.parser.add_argument("artifact_name")

        self.artifacts = []
        self.checker_task.start()

    async def load_artifacts(self):
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

        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
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
            ) as c:
                return [asdict(self.Artifact(art["id"], fullname(art), fullname_en(art))) for art in await c.fetchall()]

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
        art_desc = await self.describe_artifact(art)
        embed = discord.Embed(
            title=discord.utils.escape_markdown(art_desc[0]),
            description=discord.utils.escape_markdown(art_desc[1]))
        await ctx.reply(embed=embed)

    async def send_error(self, ctx: commands.Context, error_msg: str):
        embed = discord.Embed(title=error_msg, color=discord.Color.red())
        await ctx.reply(embed=embed)

    async def describe_artifact(self, art: Artifact):
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                '''
SELECT
    *
FROM
    a_info
    JOIN activation_info ON a_info.activate_flag = activation_info.flag
WHERE
    a_info.id = :id
''',
                    {'id': art["id"]}) as c:
                a_info = await c.fetchone()
            flags = await conn.execute_fetchall(
                '''
SELECT
    *
FROM
    a_info_flags
    JOIN flag_info ON a_info_flags.flag = flag_info.name
WHERE
    a_info_flags.id = :id
ORDER BY
    flag_group,
    id_in_group
''',
                {'id': art["id"]})

        main = f"[{art['id']}] ★{art['fullname']}"
        if a_info["is_melee_weapon"]:
            main += f" ({a_info['base_dam']})"
        elif a_info["range_weapon_mult"] > 0:
            main += f" (x{a_info['range_weapon_mult']})"
        main += self.describe_to_hit_dam(a_info)
        main += self.describe_ac(a_info)

        main += f" / {art['fullname_en']}"

        detail = self.describe_flag_group(flags, f"{a_info['pval']:+}の修正: ", 'BONUS')
        detail += self.describe_flag_group(flags, "対: ", 'SLAYING')
        detail += self.describe_flag_group(flags, "武器属性: ", 'BRAND')
        detail += self.describe_flag_group(flags, "免疫: ", 'IMMUNITY')
        detail += self.describe_flag_group(flags, "耐性: ", 'RESISTANCE')
        detail += self.describe_flag_group(flags, "維持: ", 'SUSTAIN_STATUS')
        detail += self.describe_flag_group(flags, "感知: ", 'ESP')
        detail += self.describe_flag_group(flags, "", 'POWER')
        detail += self.describe_flag_group(flags, "", 'MISC')
        detail += self.describe_flag_group(flags, "", 'CURSE')
        detail += self.describe_flag_group(flags, "追加: ", 'XTRA')
        detail += self.describe_activation(a_info)
        detail += "\n"
        detail += f"階層: {a_info['depth']}, 希少度: {a_info['rarity']}, {a_info['weight']/20:.1f} kg, ${a_info['cost']}"

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
        )+"\n "

    def describe_activation(self, a_info: dict):
        if a_info["activate_flag"] == "NONE":
            return ""
        timeout = (
            self.describe_activation_timeout(a_info['timeout'], a_info['dice']) or
            self.describe_activation_timeout_special(a_info['activate_flag'])
        )
        return f"\n発動: {a_info['desc']} : {timeout}\n"

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

    async def download_file(self, filepath: str) -> Optional[str]:
        url = self.hengband_src_url + filepath
        async with self.client_session.get(url, headers={'if-none-match': self.etags.get(filepath, "")}) as res:
            if res.status != 200:
                return None
            self.etags[filepath] = res.headers.get('etag', "")
            return await res.text()

    @tasks.loop(seconds=300)
    async def checker_task(self) -> None:
        file_list = ['lib/edit/a_info.txt', 'lib/edit/k_info.txt', 'src/object-enchant/activation-info-table.c']
        updaters = [
            ArtifactInfoReader.ArtifactInfoReader().create_a_info_table,
            KindInfoReader.KindInfoReader().create_k_info_table,
            ActivationInfoReader.ActivationInfoReader().create_activation_info_table,
        ]
        downloaded_files = await asyncio.gather(*[self.download_file(f) for f in file_list])

        for text, updater in zip(downloaded_files, updaters):
            if text:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, updater, self.db_path, text)

        if not any(downloaded_files) or not self.artifacts:
            # file_listのいずれかのファイルが更新されている、もしくはアーティファクト情報が
            # 未ロードなら、アーティファクト情報を読み込む
            self.artifacts = await self.load_artifacts()

    def output_test(self):
        for art in self.artifacts:
            print(self.describe_artifact(art))


def setup(bot):
    bot.add_cog(ArtifactSpoiler(bot, bot.ext))
