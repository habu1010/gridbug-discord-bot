import asyncio
import logging
import logging.handlers
import queue
import traceback
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands, tasks

from utils import MAX_MESSAGE_LENGTH

if TYPE_CHECKING:
    from bot import Bot


class ChannelLogger(commands.Cog):
    # ログを送るコードブロックと、Discord のメッセージの上限からその囲みの分を引いた長さ
    CODE_BLOCK = "```{}```"
    MAX_LOG_LENGTH = MAX_MESSAGE_LENGTH - len(CODE_BLOCK.format(""))

    def __init__(self, bot: commands.Bot, bot_config: dict[str, Any]):
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

    async def send_log(self, log: str) -> None:
        if not isinstance(self._log_channel_id, int):
            return

        channel = self._bot.get_channel(self._log_channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            return

        await channel.send(self.CODE_BLOCK.format(self.shorten(log)))

    @classmethod
    def shorten(cls, log: str) -> str:
        """上限を超えるログは、中ほどを省略して先頭と末尾を残す

        トレースバック付きのログは上限を超えやすい。先頭にはログのメッセージが、
        末尾には例外の種類と内容があるので、両方を残す。
        """
        if len(log) <= cls.MAX_LOG_LENGTH:
            return log
        omission = "\n...\n"
        half = (cls.MAX_LOG_LENGTH - len(omission)) // 2
        return log[:half] + omission + log[-half:]

    @tasks.loop()
    async def logger_task(self) -> None:
        loop = asyncio.get_running_loop()
        record = await loop.run_in_executor(None, lambda: self._logging_queue.get())
        try:
            await self.send_log(record.message)
        except Exception:
            # 送信に失敗してもタスクを止めない (止まると以降のログが全て届かなくなる)。
            # logging に出すと自分自身に回ってくるので、標準エラー出力に出す
            traceback.print_exc()

    @logger_task.before_loop
    async def before_logger_task(self) -> None:
        await self._bot.wait_until_ready()


async def setup(bot: "Bot") -> None:
    await bot.add_cog(ChannelLogger(bot, bot.ext))
