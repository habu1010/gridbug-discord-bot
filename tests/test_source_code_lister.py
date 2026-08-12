"""SourceCodeLister のテスト

表示行の指定 (NN-MM / NN- / -MM / NN) の解釈と、
ソース取得からコードブロック生成までを検証する。
"""

import discord
import pytest
from conftest import FakeClientSession, FakeResponse

import SourceCodeLister
from SourceCodeLister import SourceCodeLister as Cog

SRC_URL = "https://example.invalid/hengband/master/"
SRC = "\n".join(f"line{i}" for i in range(1, 51))


@pytest.fixture
def cog() -> Cog:
    return Cog({"src_url": SRC_URL})


class Test_parse_display_lines:
    @pytest.mark.parametrize(
        ("display_lines", "expected"),
        [
            ("10-20", (10, 20)),  # NN-MM
            ("10-", (10, 19)),  # NN- は10行
            ("-20", (11, 20)),  # -MM は10行
            ("10", (10, 10)),  # NN は1行のみ
            ("1-1", (1, 1)),
            ("-5", (1, 5)),  # 先頭が1行目を下回らない
            ("5-100", (5, 35)),  # 30行を超える範囲は制限される
            ("5-35", (5, 35)),  # ちょうど30行差は制限されない
        ],
    )
    def test_行指定の解釈(self, cog, display_lines, expected):
        assert cog.parse_display_lines(display_lines) == expected

    @pytest.mark.parametrize(
        "display_lines", ["abc", "", "-", "10abc", "abc10", "1.5", "0", "0-5"]
    )
    def test_解釈できない指定はNoneを返す(self, cog, display_lines):
        # 呼び出し側は None であればヘルプを表示する
        assert cog.parse_display_lines(display_lines) is None


class Test_srclistコマンド:
    def patch_session(self, monkeypatch, session):
        monkeypatch.setattr(
            SourceCodeLister.aiohttp, "ClientSession", lambda *a, **kw: session
        )

    async def test_指定範囲を行番号付きで表示する(self, monkeypatch, cog, ctx):
        self.patch_session(monkeypatch, FakeClientSession(FakeResponse(200, SRC)))

        await Cog.srclist.callback(cog, ctx, "src/main.cpp", "3-5")

        content = ctx.last_reply["content"]
        assert content.startswith("```c\n")
        assert content.endswith("\n```")
        assert "   3  line3" in content
        assert "   5  line5" in content
        assert "line6" not in content

    async def test_取得先URLはsrc_urlとパスの連結(self, monkeypatch, cog, ctx):
        session = FakeClientSession(FakeResponse(200, SRC))
        self.patch_session(monkeypatch, session)

        await Cog.srclist.callback(cog, ctx, "src/main.cpp", "1")

        assert session.requests[0]["url"] == SRC_URL + "src/main.cpp"

    async def test_引数が足りなければヘルプを表示する(self, monkeypatch, cog, ctx):
        self.patch_session(monkeypatch, FakeClientSession(FakeResponse(200, SRC)))

        await Cog.srclist.callback(cog, ctx, "src/main.cpp")

        assert ctx.help_calls
        assert ctx.replies == []

    async def test_行指定が不正ならヘルプを表示する(self, monkeypatch, cog, ctx):
        # 修正前は int('') で ValueError になっていた
        self.patch_session(monkeypatch, FakeClientSession(FakeResponse(200, SRC)))

        await Cog.srclist.callback(cog, ctx, "src/main.cpp", "abc")

        assert ctx.help_calls
        assert ctx.replies == []

    async def test_ファイルが見つからなければエラーを返す(self, monkeypatch, cog, ctx):
        self.patch_session(monkeypatch, FakeClientSession(FakeResponse(404)))

        await Cog.srclist.callback(cog, ctx, "src/not-exist.cpp", "1-5")

        embed = ctx.last_reply["embed"]
        assert embed.title == "ソースファイルが見つかりません"
        assert embed.color == discord.Color.red()

    async def test_範囲外の行を指定するとエラーを返す(self, monkeypatch, cog, ctx):
        self.patch_session(monkeypatch, FakeClientSession(FakeResponse(200, SRC)))

        await Cog.srclist.callback(cog, ctx, "src/main.cpp", "100-110")

        assert ctx.last_reply["embed"].title == "指定した行はありません"


class Test_send_error:
    async def test_赤色のEmbedで返信される(self, cog, ctx):
        await cog.send_error(ctx, "エラー")

        assert ctx.last_reply["embed"].color == discord.Color.red()
