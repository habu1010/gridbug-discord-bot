import os

import discord
from discord.ext import commands, tasks

import ListSearch
import MonsterInfo
from ErrorCatchingArgumentParser import ErrorCatchingArgumentParser


class MonsterSpoiler(commands.Cog):
    def __init__(self, bot: commands.Bot, config: dict):
        self.mon_info_url = config["mon_info_url"]
        self.m_info = MonsterInfo.MonsterInfo(
            os.path.expanduser(config["mon_info_db_path"])
        )
        self.bot = bot
        self.mon_info_list = []

        self.parser = ErrorCatchingArgumentParser(prog="$mon", add_help=False)
        self.parser.add_argument("-e", "--english", action="store_true")
        self.parser.add_argument("monster_name")

        self.checker_task.start()

    @commands.command(usage="[-e] monster_name")
    async def mon(self, ctx: commands.Context, *args):
        """モンスターを検索する

        モンスターを名称の一部で検索し、情報を表示します。
        複数のモンスターがヒットした場合は候補を表示し、リアクションにより選択します。
        一件もヒットしなかった場合は、あいまい検索により候補を表示します。

        positional arguments:
          monster_name          検索するモンスターの名称の一部

        optional arguments:
          -e, --english         英語名で検索する
        """

        try:
            parse_result = self.parser.parse_args(args)
        except Exception:
            await ctx.send_help(ctx.command)
            return

        await ListSearch.search(
            ctx,
            self.send_mon_info,
            self.send_error,
            None,
            self.mon_info_list,
            parse_result.monster_name,
            "name",
            "english_name",
            parse_result.english,
        )

    async def create_mon_info_embed(self, mon_info: dict):
        title = "[U] " if mon_info["is_unique"] else ""
        title += "{name} / {english_name} ({symbol})".format(**mon_info)
        description = """
ID:{id}  階層:{level}  レア度:{rarity}  加速:{speed}  HP:{hp}  AC:{ac}  Exp:{exp}

""".format(
            **mon_info
        )
        description += await self.m_info.get_monster_detail(mon_info["id"])
        return discord.Embed(title=title, description=description)

    async def send_error(self, ctx: commands.Context, error_msg: str):
        embed = discord.Embed(title=error_msg, color=discord.Color.red())
        await ctx.reply(embed=embed)

    async def send_mon_info(self, ctx: commands.Context, mon_info, _):
        await ctx.reply(embed=await self.create_mon_info_embed(mon_info))

    @tasks.loop(seconds=300)
    async def checker_task(self):
        updated = await self.m_info.check_update(self.mon_info_url)
        if updated or not self.mon_info_list:
            self.mon_info_list = await self.m_info.get_monster_info_list()


async def setup(bot):
    await bot.add_cog(MonsterSpoiler(bot, bot.ext))
