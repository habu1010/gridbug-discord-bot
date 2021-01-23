import json
import logging
import os

from discord.ext import commands

with open(os.path.expanduser('~/.bot-config.json'), 'r') as f:
    bot_config = json.load(f)

logging.basicConfig(
    level=bot_config.get('logging_level', 'WARNING'))

bot = commands.Bot('$')

for ext in bot_config.get("extensions"):
    bot.ext = ext
    bot.load_extension(ext["name"])

bot.run(bot_config["token"])
