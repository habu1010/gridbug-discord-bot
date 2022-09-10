import asyncio
import logging
import logging.handlers

import discord
from discord.ext import commands, tasks


class ChannelLogger(commands.Cog):
    def __init__(self, bot: commands.Bot, bot_config: dict):
        self._bot = bot
        self._logging_queue = asyncio.Queue()

        logger = logging.getLogger()
        handler = logging.handlers.QueueHandler(self._logging_queue)
        handler.setFormatter(
            logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
        )
        logger.addHandler(handler)

        self._log_channel_id = bot_config.get("channel_id", "")

        self.logger_task.start()

    async def send_log(self, log: str):
        channel: discord.abc.GuildChannel = self._bot.get_channel(self._log_channel_id)
        await channel.send(f"```{log}```")

    @tasks.loop()
    async def logger_task(self) -> None:
        record: logging.LogRecord = await self._logging_queue.get()
        await self.send_log(record.message)

    @logger_task.before_loop
    async def before_logger_task(self) -> None:
        await self._bot.wait_until_ready()


def setup(bot):
    bot.add_cog(ChannelLogger(bot, bot.ext))
