import asyncio
import logging
import os
from typing import Any

import discord
import yaml
from discord.ext import commands


class Bot(commands.Bot):
    # 現在ロード中の拡張の設定。load_extension() の直前に代入され、
    # 各モジュールの setup() の中だけで有効な一時的な受け渡し用の属性。
    ext: dict[str, Any]

    def __init__(
        self,
        command_prefix: list[str],
        *,
        intents: discord.Intents,
        bot_config: dict[str, Any],
    ):
        super().__init__(command_prefix, intents=intents)
        self.bot_config = bot_config

    async def setup_hook(self) -> None:
        for ext in self.bot_config.get("extensions", []):
            if (extension_name := ext.get("name")) is None:
                continue
            if logging_level := ext.get("logging_level"):
                logging.getLogger(extension_name).setLevel(logging_level)
            self.ext = ext
            await self.load_extension(extension_name)


async def main() -> None:
    with open(os.path.expanduser("~/.bot-config.yml"), "r") as f:
        bot_config = yaml.full_load(f)

    logging.basicConfig(level=bot_config.get("logging_level", "WARNING"))

    intents = discord.Intents.default()
    intents.message_content = True

    bot = Bot(
        ["$", "!", "?", "＄", "！", "？"],
        intents=intents,
        bot_config=bot_config,
    )
    await bot.start(bot_config["token"])


if __name__ == "__main__":
    asyncio.run(main())
