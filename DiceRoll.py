import random
import re

import discord
from discord.ext import commands


class DiceRoll(commands.Cog):
    # 振る回数と面数の上限。結果の合計と内訳が Embed の上限 (title 256文字、
    # description 4096文字) に収まるようにする
    MAX_DICE = 100
    MAX_SIDE = 10**9

    def __init__(self) -> None:
        self.diceroll_pattern = re.compile(r"^(\d+)[Dd](\d+)$")
        self.rng = random.Random()

    @commands.command()
    async def roll(self, ctx: commands.Context, arg: str) -> None:
        m = self.diceroll_pattern.match(arg)
        if m is None:
            return

        dice = int(m.group(1))
        side = int(m.group(2))
        if dice > 0 and side > 0:
            result_msg = self._roll(dice, side)
            await ctx.reply(embed=result_msg)

    def _roll(self, dice: int, side: int) -> discord.Embed:
        if dice > self.MAX_DICE:
            return discord.Embed(
                title="振る回数が多すぎます", color=discord.Color.red()
            )
        if side > self.MAX_SIDE:
            return discord.Embed(title="面の数が多すぎます", color=discord.Color.red())
        roll_results = [self.rng.randint(1, side) for _ in range(dice)]
        roll_sum = sum(roll_results)
        result_seq = "[" + ",".join(str(i) for i in roll_results) + "]"
        return discord.Embed(title=roll_sum, description=result_seq)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DiceRoll())
