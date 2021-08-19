import discord
from discord.ext import commands

from ErrorCatchingArgumentParser import ErrorCatchingArgumentParser


class Vote(commands.Cog):
    NUM_EMOJIS = [
        '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟'
    ]

    def __init__(self, bot: commands.Bot):
        self.parser = ErrorCatchingArgumentParser(prog="translate", add_help=False)
        self.parser.add_argument("title")
        self.parser.add_argument("candidates", nargs='+')

    @commands.command(usage="title candidate1 [candidate2 ...]")
    async def vote(self, ctx: commands.Context, *args):
        """投票を行います

        positional arguments:
          title                 投票のタイトル
          candidateN            N 個目の候補 (最大10個)
        """

        try:
            parse_result = self.parser.parse_args(args)
        except Exception:
            await ctx.send_help(ctx.command)
            return

        vote_title = parse_result.title
        candidates_text = '\n'.join([n + " " + c for n, c in zip(self.NUM_EMOJIS, parse_result.candidates)])
        candidates_num = len(parse_result.candidates)

        embed = discord.Embed(title=vote_title, description=candidates_text)
        vote_msg = await ctx.reply(embed=embed)
        for num in self.NUM_EMOJIS[:candidates_num]:
            await vote_msg.add_reaction(num)


def setup(bot):
    bot.add_cog(Vote(bot))
