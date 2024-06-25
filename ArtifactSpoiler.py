import asyncio
import os
from collections.abc import Iterable
from typing import Dict, List, Optional

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
    def __init__(self, base_url: str, db_path: str):
        self.base_url = base_url
        self.db_path = db_path
        self.etags: Dict[str, str] = {}

        FlagInfoReader.FlagInfoReader().create_flag_info_table(
            db_path,
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "flag_info.txt"),
        )

        self._artifacts: List[Dict] = []

    @property
    def artifacts(self):
        return self._artifacts

    async def load_artifacts(self) -> List[Dict]:

        def fullname(art: aiosqlite.Row):
            a = art["a_name"]
            k = art["k_name"]
            if art["is_fullname"]:
                return a
            elif a.startswith("『"):
                return k + a
            return a + k

        def fullname_en(art: aiosqlite.Row):
            a = art["a_name_en"]
            k = art["k_name_en"]
            f = a if art["is_fullname"] else f"{k} {a}"
            return f.replace("&", "The").replace("~", "")

        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                """
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
"""
            ) as c:
                return [
                    {
                        "id": art["id"],
                        "fullname": fullname(art),
                        "fullname_en": fullname_en(art),
                    }
                    for art in await c.fetchall()
                ]

    async def describe_artifact(self, art: Dict):
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                """
SELECT
    *
FROM
    a_info
    JOIN activation_info ON a_info.activate_flag = activation_info.flag
WHERE
    a_info.id = :id
""",
                {"id": art["id"]},
            ) as c:
                a_info = await c.fetchone()
            flags = await conn.execute_fetchall(
                """
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
""",
                {"id": art["id"]},
            )

        main = f"[{art['id']}] ★{art['fullname']}"
        if not a_info:
            return (main, "詳細情報が見つかりませんでした")
        if a_info["is_melee_weapon"]:
            main += f" ({a_info['base_dam']})"
        elif a_info["range_weapon_mult"] > 0:
            main += f" (x{a_info['range_weapon_mult']})"
        main += self.describe_to_hit_dam(a_info)
        main += self.describe_ac(a_info)

        main += f" / {art['fullname_en']}"

        detail = self.describe_flag_group(flags, f"{a_info['pval']:+}の修正: ", "BONUS")
        detail += self.describe_flag_group(flags, "対: ", "SLAYING")
        detail += self.describe_flag_group(flags, "武器属性: ", "BRAND")
        detail += self.describe_flag_group(flags, "免疫: ", "IMMUNITY")
        detail += self.describe_flag_group(flags, "耐性: ", "RESISTANCE")
        detail += self.describe_flag_group(flags, "弱点: ", "VULNERABILITY")
        detail += self.describe_flag_group(flags, "維持: ", "SUSTAIN_STATUS")
        detail += self.describe_flag_group(flags, "感知: ", "ESP")
        detail += self.describe_flag_group(flags, "", "POWER")
        detail += self.describe_flag_group(flags, "", "MISC")
        detail += self.describe_flag_group(flags, "", "CURSE")
        detail += self.describe_flag_group(flags, "追加: ", "XTRA")
        detail += self.describe_activation(a_info)
        detail += "\n"
        detail += (
            f"階層: {a_info['depth']}, 希少度: {a_info['rarity']},"
            f" {a_info['weight']/20:.1f} kg, ${a_info['cost']}"
        )

        return (main, detail)

    def describe_to_hit_dam(self, a_info: aiosqlite.Row):
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

    def describe_ac(self, a_info: aiosqlite.Row):
        res = ""
        if a_info["is_protective_equipment"] or a_info["base_ac"] > 0:
            res += f" [{a_info['base_ac']},{a_info['to_ac']:+}]"
        elif a_info["to_ac"] != 0:
            res += f" [{a_info['to_ac']:+}]"
        return res

    def describe_flag_group(
        self, flags: Iterable[aiosqlite.Row], head: str, group_name: str
    ):
        if group_name not in [flag["flag_group"] for flag in flags]:
            return ""
        return (
            f"{head}"
            + ", ".join(
                [
                    flag["description"]
                    for flag in flags
                    if flag["flag_group"] == group_name
                ]
            )
            + "\n "
        )

    def describe_activation(self, a_info: aiosqlite.Row):
        if a_info["activate_flag"] == "NONE":
            return ""
        timeout = self.describe_activation_timeout(
            a_info["timeout"], a_info["dice"]
        ) or self.describe_activation_timeout_special(a_info["activate_flag"])
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
        DICT = {"TERROR": "3*(レベル+10) ターン毎", "MURAMASA": "確率50%で壊れる"}
        return DICT.get(flag, "不明")

    async def download_file(
        self, session: aiohttp.ClientSession, filepath: str
    ) -> Optional[str]:
        url = f"{self.base_url}/{filepath}"
        async with session.get(
            url, headers={"if-none-match": self.etags.get(filepath, "")}
        ) as res:
            if res.status != 200:
                return None
            self.etags[filepath] = res.headers.get("etag", "")
            return await res.text()

    async def check_for_updates(self, session: aiohttp.ClientSession) -> None:
        file_list = [
            "lib/edit/ArtifactDefinitions.jsonc",
            "lib/edit/BaseitemDefinitions.jsonc",
            "src/object-enchant/activation-info-table.cpp",
        ]
        updaters = [
            ArtifactInfoReader.ArtifactInfoReader().create_a_info_table,
            KindInfoReader.KindInfoReader().create_k_info_table,
            ActivationInfoReader.ActivationInfoReader().create_activation_info_table,
        ]
        downloaded_files = await asyncio.gather(
            *[self.download_file(session, f) for f in file_list]
        )

        for text, updater in zip(downloaded_files, updaters):
            if text:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, updater, self.db_path, text)

        if any(downloaded_files) or not self._artifacts:
            # file_listのいずれかのファイルが更新されている、もしくはアーティファクト情報が
            # 未ロードなら、アーティファクト情報を読み込む
            self._artifacts = await self.load_artifacts()

    def output_test(self):
        for art in self._artifacts:
            print(self.describe_artifact(art))


class ArtifactSpoilerCog(commands.Cog):
    BRANCHES = ["master", "develop"]

    def __init__(self, bot: commands.Command, config: dict):
        self.bot = bot

        self.spoilers: Dict[str, ArtifactSpoiler] = {}
        for branch in self.BRANCHES:
            base_url = f"{config['hengband_src_url']}/{branch}"
            db_path = os.path.join(
                os.path.expanduser(config["db_dir"]), f"art-info-{branch}.db"
            )
            self.spoilers[branch] = ArtifactSpoiler(base_url, db_path)

        self.parser = ErrorCatchingArgumentParser(prog="art", add_help=False)
        self.parser.add_argument("-d", "--develop", action="store_true")
        self.parser.add_argument("-e", "--english", action="store_true")
        self.parser.add_argument("artifact_name")

        self.checker_task.start()

    @commands.command(usage="[-e] artifact_name")
    async def art(self, ctx: commands.Context, *args):
        """アーティファクトを検索する

        アーティファクトを名称の一部で検索し、情報を表示します。
        複数のアーティファクトが見つかった場合は候補を表示し、リアクションで選択します。
        一件もヒットしなかった場合は、あいまい検索により候補を表示します。

        positional arguments:
          artifact_name         検索するアーティファクトの名称の一部

        optional arguments:
          -d, --develop         開発(develop)ブランチを検索する
          -e, --english         英語名で検索する
        """

        try:
            parse_result = self.parser.parse_args(args)
        except Exception:
            await ctx.send_help(ctx.command)
            return

        spoiler = (
            self.spoilers["develop"]
            if parse_result.develop
            else self.spoilers["master"]
        )

        await ListSearch.search(
            ctx,
            self.send_artifact_info,
            self.send_error,
            spoiler,
            spoiler.artifacts,
            parse_result.artifact_name,
            "fullname",
            "fullname_en",
            parse_result.english,
        )

    async def send_artifact_info(
        self, ctx: commands.Context, art: dict, spoiler: ArtifactSpoiler
    ):
        art_desc = await spoiler.describe_artifact(art)
        embed = discord.Embed(
            title=discord.utils.escape_markdown(art_desc[0]),
            description=discord.utils.escape_markdown(art_desc[1]),
        )
        await ctx.reply(embed=embed)

    async def send_error(self, ctx: commands.Context, error_msg: str):
        embed = discord.Embed(title=error_msg, color=discord.Color.red())
        await ctx.reply(embed=embed)

    @tasks.loop(seconds=300)
    async def checker_task(self) -> None:
        async with aiohttp.ClientSession() as session:
            update_tasks = [
                spoiler.check_for_updates(session) for spoiler in self.spoilers.values()
            ]
            await asyncio.gather(*update_tasks)


async def setup(bot):
    await bot.add_cog(ArtifactSpoilerCog(bot, bot.ext))
