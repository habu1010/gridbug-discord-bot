import os

import discord
from discord.ext import commands, tasks

import ListSearch
import MonsterInfo
from ErrorCatchingArgumentParser import ErrorCatchingArgumentParser


class MonsterSpoiler(commands.Cog):
    def __init__(self, bot: commands.Bot, config: dict):
        self.mon_info_url = config["mon_info_url"]
        self.m_info = MonsterInfo.MonsterInfo(os.path.expanduser(config["mon_info_db_path"]))
        self.bot = bot

        self.parser = ErrorCatchingArgumentParser(
            prog="$mon", add_help=False,
            description="モンスターを名称の一部で検索し、情報を表示します。"
            "複数のモンスターがヒットした場合は候補を表示し、リアクションにより選択します。"
            "一件もヒットしなかった場合は、あいまい検索により候補を表示します。")
        self.parser.add_argument(
            "-e", "--english", action="store_true", default=False,
            help="英語名で検索する / Search by English name")
        self.parser.add_argument(
            "-h", "--help", action="store_true", default=False,
            help="このヘルプメッセージを表示する")
        self.parser.add_argument("name", help="検索するモンスターの名称の一部", nargs='?')

        self.checker_task.start()

    @commands.command()
    async def mon(self, ctx: commands.Context, *args):
        try:
            parse_result = self.parser.parse_args(args)
        except Exception as e:
            await self.send_error(ctx, str(e), self.parser.format_help())
            return
        if len(args) == 0 or parse_result.help:
            await self.send_error(ctx, "ヘルプ", self.parser.format_help())
            return

        choice, error_msg = await ListSearch.search(
            ctx, self.mon_info_list, parse_result.name, "name", "english_name", parse_result.english)

        if choice:
            await self.send_mon_info(ctx, choice)
        elif error_msg:
            await self.send_error(ctx, error_msg)

    async def send_error(self, ctx: commands.Context, error_msg: str):
        embed = discord.Embed(title=error_msg, color=discord.Color.red())
        await ctx.reply(embed=embed)

    async def send_mon_info(self, ctx: commands.Context, mon_info):
        title = "[U] " if mon_info["is_unique"] else ""
        title += "{name} / {english_name} ({symbol})".format(**mon_info)
        description = "ID:{id}  階層:{level}  レア度:{rarity}  加速:{speed}  HP:{hp}  AC:{ac}  Exp:{exp}\n\n"\
            .format(**mon_info)
        description += self.m_info.get_monster_detail(mon_info["id"])
        embed = discord.Embed(title=title, description=description)
        await ctx.reply(embed=embed)

    @tasks.loop(seconds=3600.0)
    async def checker_task(self):
        self.m_info.check_update(self.mon_info_url)
        self.mon_info_list = self.m_info.get_monster_info_list()


def setup(bot):
    bot.add_cog(MonsterSpoiler(bot, bot.ext))
