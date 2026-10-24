"""ChannelLogger のテスト

ChannelLogger は __init__ で logger_task を起動し、ルートロガーにハンドラを足すため、
__new__ で生成して属性を差し込む。
"""

import logging
import queue
from types import SimpleNamespace
from typing import cast

import pytest
from discord.ext import commands

from ChannelLogger import ChannelLogger

CHANNEL_ID = 12345


class FakeLogChannel:
    """送信した内容を記録するチャンネルのスタブ。fail を真にすると送信に失敗する"""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.sent: list[str] = []

    async def send(self, content: str) -> None:
        if self.fail:
            raise RuntimeError("送信失敗")
        self.sent.append(content)


@pytest.fixture(autouse=True)
def messageable_stub(monkeypatch):
    """send_log() の isinstance(channel, Messageable) をスタブで通す"""
    monkeypatch.setattr("discord.abc.Messageable", FakeLogChannel)


def make_logger(channel: FakeLogChannel) -> ChannelLogger:
    cog = ChannelLogger.__new__(ChannelLogger)
    bot = SimpleNamespace(get_channel=lambda channel_id: channel)
    cog._bot = cast(commands.Bot, bot)
    cog._logging_queue = queue.Queue()
    cog._log_channel_id = CHANNEL_ID
    return cog


def put_log(cog: ChannelLogger, message: str) -> None:
    record = logging.LogRecord("test", logging.WARNING, "", 0, message, None, None)
    record.message = message
    cog._logging_queue.put(record)


class Test_send_log:
    async def test_ログをコードブロックで送る(self):
        channel = FakeLogChannel()
        cog = make_logger(channel)

        await cog.send_log("警告")

        assert channel.sent == ["```警告```"]


class Test_shorten:
    def test_上限以内のログはそのまま(self):
        assert ChannelLogger.shorten("あ" * ChannelLogger.MAX_LOG_LENGTH) == (
            "あ" * ChannelLogger.MAX_LOG_LENGTH
        )

    def test_長いログは中ほどを省略して先頭と末尾を残す(self):
        log = "先頭" + "あ" * 3000 + "末尾"

        shortened = ChannelLogger.shorten(log)

        assert len(shortened) <= ChannelLogger.MAX_LOG_LENGTH
        assert shortened.startswith("先頭")
        assert shortened.endswith("末尾")
        assert "\n...\n" in shortened


class Test_logger_task:
    async def test_送信に失敗してもタスクは例外を出さない(self, capsys):
        cog = make_logger(FakeLogChannel(fail=True))
        put_log(cog, "警告")

        await ChannelLogger.logger_task.coro(cog)

        assert "送信失敗" in capsys.readouterr().err
