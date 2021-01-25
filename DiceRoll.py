import random
import re

from discord.ext import commands


class DiceRoll(commands.Cog):
    def __init__(self):
        self.diceroll_pattern = re.compile(r'^(\d+)[Dd](\d+)$')
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
            await ctx.reply(result_msg)

    def __roll(self, dice: int, side: int):
        if dice > 100:
            return '振る回数が多すぎます'
        roll_results = [self.rng.randint(1, side) for _ in range(dice)]
        roll_sum = sum(roll_results)
        result_seq = ','.join(str(i) for i in roll_results)
        return "{seq} = {sum}".format(seq=result_seq, sum=roll_sum)


def setup(bot):
    bot.add_cog(DiceRoll())
