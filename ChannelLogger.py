import asyncio
import logging
import logging.handlers
import queue

import discord
from discord.ext import commands, tasks


class ChannelLogger(commands.Cog):
    def __init__(self, bot: commands.Bot, bot_config: dict):
        self._bot = bot
        self._logging_queue: queue.Queue[logging.LogRecord] = queue.Queue()

        logger = logging.getLogger()
        handler = logging.handlers.QueueHandler(self._logging_queue)
        handler.setFormatter(
            logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
        )
        logger.addHandler(handler)

        self._log_channel_id = bot_config.get("channel_id", None)
        self.logger_task.start()

    async def send_log(self, log: str):
        if not isinstance(self._log_channel_id, int):
            return

        channel = self._bot.get_channel(self._log_channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            return

        await channel.send(f"```{log}```")

    @tasks.loop()
    async def logger_task(self) -> None:
        loop = asyncio.get_running_loop()
        record = await loop.run_in_executor(None, lambda: self._logging_queue.get())
        await self.send_log(record.message)

    @logger_task.before_loop
    async def before_logger_task(self) -> None:
        await self._bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(ChannelLogger(bot, bot.ext))
