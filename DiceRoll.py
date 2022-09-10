import random
import re

import discord
from discord.ext import commands


class DiceRoll(commands.Cog):
    def __init__(self):
        self.diceroll_pattern = re.compile(r"^(\d+)[Dd](\d+)$")
        self.rng = random.Random()

    @commands.command()
    async def roll(self, ctx, arg):
        m = self.diceroll_pattern.match(arg)
        if m is None:
            return

        dice = int(m.group(1))
        side = int(m.group(2))
        if dice > 0 and side > 0:
            result_msg = self.__roll(dice, side)
            await ctx.reply(embed=result_msg)

    def __roll(self, dice: int, side: int) -> discord.Embed:
        if dice > 100:
            return discord.Embed(title="振る回数が多すぎます", color=discord.Color.red())
        roll_results = [self.rng.randint(1, side) for _ in range(dice)]
        roll_sum = sum(roll_results)
        result_seq = "[" + ",".join(str(i) for i in roll_results) + "]"
        return discord.Embed(title=roll_sum, description=result_seq)


def setup(bot):
    bot.add_cog(DiceRoll())
