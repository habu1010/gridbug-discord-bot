"""setup() で必ず失敗する拡張 (tests/test_bot.py で使う)"""

from discord.ext import commands


async def setup(bot: commands.Bot) -> None:
    raise RuntimeError("setup に失敗した")
