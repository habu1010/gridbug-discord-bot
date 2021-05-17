import logging
import os

import yaml
from discord.ext import commands

with open(os.path.expanduser('~/.bot-config.yml'), 'r') as f:
    bot_config = yaml.full_load(f)

logging.basicConfig(
    level=bot_config.get('logging_level', 'WARNING'))

bot = commands.Bot(['$', '!', '?', '＄', '！', '？'])

for ext in bot_config.get("extensions"):
    bot.ext = ext
    bot.load_extension(ext["name"])
    if logging_level := ext.get("logging_level"):
        logging.getLogger(ext["name"]).setLevel(logging_level)

bot.run(bot_config["token"])
