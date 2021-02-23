import asyncio

import googletrans
from discord.ext import commands

from ErrorCatchingArgumentParser import ErrorCatchingArgumentParser


class Translator(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.translator = googletrans.Translator()

        self.parser = ErrorCatchingArgumentParser(prog="translate", add_help=False)
        self.parser.add_argument("-d", "--dest")
        self.parser.add_argument("-s", "--src")
        self.parser.add_argument("text", nargs='+')

    @commands.command(aliases=['trans', 't'], usage="[-d DEST] [-s SRC] text")
    async def translate(self, ctx: commands.Context, *args):
        """Google Translate APIを使用して文章を翻訳します / Translate text using the Google Translate API.

        positional arguments:
          text                  翻訳する文章 / The text you want to translate

        optional arguments:
          -d DEST, --dest DEST  翻訳先の言語 / The destination language you want to translate.
                                (Default: 'en', but if source language is not Japanese, 'ja')
          -s SRC, --src SRC     翻訳元の言語 / The source language you want to translate.
                                (Default: auto detect)
        """

        try:
            parse_result = self.parser.parse_args(args)
        except Exception:
            await ctx.send_help(ctx.command)
            return

        text = ' '.join(parse_result.text)
        src = parse_result.src or self.translator.detect(text).lang
        dest = parse_result.dest or ('ja' if src != 'ja' else 'en')

        try:
            loop = asyncio.get_running_loop()
            translated = await loop.run_in_executor(None, self.translator.translate, text, dest, src)
            msg = f"[{translated.src} → {translated.dest}] {translated.text}"
            await ctx.reply(msg)
        except Exception as e:
            error_msg = str(e)
            await ctx.reply(error_msg)


def setup(bot):
    bot.add_cog(Translator(bot))
