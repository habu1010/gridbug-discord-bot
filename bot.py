import asyncio
import logging
import os

import discord
import yaml
from discord.ext import commands


class Bot(commands.Bot):
    def __init__(self, command_prefix, *, intents: discord.Intents, bot_config: dict):
        super().__init__(command_prefix, intents=intents)
        self.bot_config = bot_config

    async def setup_hook(self):
        for ext in self.bot_config.get("extensions", []):
            if (extension_name := ext.get("name")) is None:
                continue
            if logging_level := ext.get("logging_level"):
                logging.getLogger(extension_name).setLevel(logging_level)
            self.ext = ext
            await self.load_extension(extension_name)


async def main():
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
