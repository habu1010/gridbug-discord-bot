"""Translator のテスト

googletrans の翻訳 (HTTP 通信) は、翻訳結果を返すだけのスタブに差し替える。
"""

from types import SimpleNamespace
from typing import Any, cast

import pytest

from Translator import Translator

# Command.callback は型の上では cog を受け取らないので Any にキャストして呼ぶ
translate_callback = cast(Any, Translator.translate.callback)


@pytest.fixture
def cog(monkeypatch) -> Translator:
    translator = Translator()

    def translate(text, dest, src):
        return SimpleNamespace(src=src, dest=dest, text=text * 3)

    monkeypatch.setattr(translator.translator, "translate", translate)
    return translator


class Test_translate:
    async def test_翻訳結果を言語つきで返信する(self, cog, ctx):
        await translate_callback(cog, ctx, "-s", "ja", "-d", "en", "テスト")

        assert ctx.last_reply["content"] == "[ja → en] テストテストテスト"

    async def test_長い翻訳結果はメッセージの上限に切り詰める(self, cog, ctx):
        await translate_callback(cog, ctx, "-s", "ja", "あ" * 1000)

        # Discord のメッセージは2000文字が上限
        content = ctx.last_reply["content"]
        assert len(content) == 2000
        assert content.endswith("...")

    async def test_メッセージの無い例外でも空でない返信をする(
        self, cog, ctx, monkeypatch
    ):
        def fail(text, dest, src):
            raise TimeoutError()

        monkeypatch.setattr(cog.translator, "translate", fail)

        await translate_callback(cog, ctx, "-s", "ja", "テスト")

        assert ctx.last_reply["content"] == "TimeoutError()"
