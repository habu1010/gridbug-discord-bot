"""Bot のテスト

Discord には接続せず、setup_hook() による拡張の読み込みだけを検証する。
スラッシュコマンドの登録 (tree.sync) は通信するので差し替える。
"""

import logging

import discord
import pytest
from discord.ext import commands

from bot import Bot


@pytest.fixture
def sync_calls() -> list[None]:
    """差し替えた tree.sync() が呼ばれた記録"""
    return []


@pytest.fixture
def make_bot(monkeypatch, sync_calls):
    def make(extensions: object) -> Bot:
        bot = Bot(
            ["$"],
            intents=discord.Intents.default(),
            bot_config={"extensions": extensions},
        )

        async def sync():
            sync_calls.append(None)
            return []

        monkeypatch.setattr(bot.tree, "sync", sync)
        return bot

    return make


def bot_records(caplog) -> list[logging.LogRecord]:
    """bot.py が出したログ (discord.py などのログは除く)"""
    return [r for r in caplog.records if r.name == "bot"]


def bot_logs(caplog) -> list[str]:
    return [message for name, _, message in caplog.record_tuples if name == "bot"]


class Test_setup_hook:
    async def test_設定の拡張を読み込む(self, make_bot):
        bot = make_bot([{"name": "DiceRoll"}])

        await bot.setup_hook()

        assert "DiceRoll" in bot.extensions

    async def test_読み込めない拡張があっても残りを読み込む(
        self, make_bot, caplog, sync_calls
    ):
        bot = make_bot([{"name": "NoSuchExtension"}, {"name": "DiceRoll"}])

        with caplog.at_level(logging.ERROR):
            await bot.setup_hook()

        assert "DiceRoll" in bot.extensions
        # 読み込めた拡張のスラッシュコマンドは登録する
        assert sync_calls == [None]
        assert "NoSuchExtension" not in bot.extensions
        assert bot_logs(caplog) == ["拡張 NoSuchExtension を読み込めませんでした"]
        assert bot_records(caplog)[0].exc_info is not None

    async def test_setupで失敗した拡張があっても残りを読み込む(self, make_bot, caplog):
        # 本物の Cog は __init__ でタスクを起動するものがあるので、
        # setup() で必ず失敗するテスト用の拡張を使う
        bot = make_bot([{"name": "failing_extension"}, {"name": "DiceRoll"}])

        with caplog.at_level(logging.ERROR):
            await bot.setup_hook()

        assert "DiceRoll" in bot.extensions
        assert bot_logs(caplog) == ["拡張 failing_extension を読み込めませんでした"]
        # モジュールが見つからなかったのではなく、setup() で失敗したこと
        exc_info = bot_records(caplog)[0].exc_info
        assert exc_info is not None and exc_info[0] is commands.ExtensionFailed

    @pytest.mark.parametrize(
        "broken, name",
        [
            # 名前と設定の辞書ではなく、名前だけを書いた (文字列はログに出さない)
            ("DiceRoll", "(名前を読めない str の設定)"),
            # name の書き間違い
            ({"nmae": "DiceRoll"}, "(名前を読めない dict の設定)"),
            # インデントの誤りで、辞書ではなくリストになった (中身はログに出さない)
            (
                [{"name": "DiceRoll"}, {"api_key": "SECRET"}],
                "(名前を読めない list の設定)",
            ),
            # ログレベルの書き間違い (その拡張は読み込まない)
            ({"name": "DiceRoll", "logging_level": "VERBOSE"}, "DiceRoll"),
        ],
    )
    async def test_設定を書き間違えた拡張があっても残りを読み込む(
        self, make_bot, caplog, broken, name
    ):
        bot = make_bot([broken, {"name": "SourceCodeLister", "src_url": ""}])

        with caplog.at_level(logging.ERROR):
            await bot.setup_hook()

        assert "SourceCodeLister" in bot.extensions
        assert bot_logs(caplog) == [f"拡張 {name} を読み込めませんでした"]

    async def test_拡張のロガーにログレベルを設定する(self, make_bot):
        logger = logging.getLogger("DiceRoll")
        original_level = logger.level
        bot = make_bot([{"name": "DiceRoll", "logging_level": "DEBUG"}])

        try:
            await bot.setup_hook()

            assert logger.level == logging.DEBUG
        finally:
            # ロガーのレベルはプロセス全体に残るので元に戻す (setLevel で戻すと
            # isEnabledFor の結果のキャッシュも消える)
            logger.setLevel(original_level)

    @pytest.mark.parametrize("extensions", [None, []])
    async def test_拡張が無くても起動する(self, make_bot, sync_calls, extensions):
        bot = make_bot(extensions)

        await bot.setup_hook()

        assert sync_calls == [None]
