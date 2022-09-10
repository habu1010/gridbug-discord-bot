import re

import aiohttp
import discord
from discord.ext import commands

from ErrorCatchingArgumentParser import ErrorCatchingArgumentParser


class SourceCodeLister(commands.Cog):
    def __init__(self, bot: commands.Bot, config: dict):
        self.src_url = config["src_url"]

        self.parser = ErrorCatchingArgumentParser(prog="srclist", add_help=False)
        self.parser.add_argument("filepath")
        self.parser.add_argument("display_lines")

    @commands.command(usage="filepath display_lines")
    async def srclist(self, ctx: commands.Context, *args):
        """変愚蛮怒のソースファイルの一部を表示する

        positional arguments:
          filepath              ソースファイルのパス
          display_lines         表示する行

        display_linesは、NN行目からMM行目までの表示を NN-MM の形で指定する。
        NNもしくはMMは省略でき、省略した場合はNNから10行あるいはMMまで10行を
        表示する。-も省略した場合はNNの1行のみを表示する。
        30行を超える範囲が指定された場合は30行に制限される。
        """

        try:
            parse_result = self.parser.parse_args(args)
        except Exception:
            await ctx.send_help(ctx.command)
            return

        start, end = self.parse_display_lines(parse_result.display_lines)
        if not start:
            await ctx.send_help(ctx.command)
            return

        async with aiohttp.ClientSession() as session:
            async with session.get(self.src_url + parse_result.filepath) as res:
                if res.status != 200:
                    await self.send_error(ctx, "ソースファイルが見つかりません")
                    return
                src = await res.text()

        display_lines = [
            f"{i:4}  {l}"
            for i, l in enumerate(src.splitlines()[start - 1 : end], start)
        ]
        if not display_lines:
            await self.send_error(ctx, "指定した行はありません")
            return

        msg = "```c\n" + "\n".join(display_lines) + "\n```"
        await ctx.reply(msg)

    def parse_display_lines(self, display_lines: str) -> tuple:
        m = re.match(r"^(\d*)(-?)(\d*)", display_lines)
        if not m:
            return (None, None)

        if m[1] and m[2] and m[3]:
            # NN-MM
            start = int(m[1])
            end = min(int(m[3]), start + 30)
        elif m[1] and m[2] and not m[3]:
            # NN-
            start = int(m[1])
            end = start + 9
        elif not m[1] and m[2] and m[3]:
            # -MM
            end = int(m[3])
            start = max(end - 9, 1)
        else:
            start = int(m[1])
            end = start

        return (start, end)

    async def send_error(self, ctx: commands.Context, error_msg: str):
        embed = discord.Embed(title=error_msg, color=discord.Color.red())
        await ctx.reply(embed=embed)


def setup(bot):
    bot.add_cog(SourceCodeLister(bot, bot.ext))
