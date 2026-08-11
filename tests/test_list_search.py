"""ListSearch のテスト

名前検索は「部分一致 → 完全一致が1件ならそれを採用 → 候補10件以下ならボタンで選択
→ 0件ならあいまい検索」という流れ。

discord.ui.View の生成には実行中のイベントループが必要なため、全て非同期テストにする。
"""

import discord
import pytest

import ListSearch
from ListSearch import SelectButton, SelectView

ITEMS = [
    {"name": "グリッド・バグ", "english_name": "Grid bug"},
    {"name": "大グリッド・バグ", "english_name": "Giant grid bug"},
    {"name": "大ネズミ", "english_name": "Giant rat"},
    {"name": "農夫マゴット", "english_name": "Farmer Maggot"},
]


class SearchResult:
    """search() のコールバック呼び出しを記録する"""

    def __init__(self):
        self.found = []
        self.errors = []

    async def on_found(self, ctx, item, arg):
        self.found.append({"ctx": ctx, "item": item, "arg": arg})

    async def on_error(self, ctx, msg):
        self.errors.append(msg)


@pytest.fixture
def result() -> SearchResult:
    return SearchResult()


async def search(ctx, result, items, search_str, english=False, arg="ARG"):
    await ListSearch.search(
        ctx,
        result.on_found,
        result.on_error,
        arg,
        items,
        search_str,
        "name",
        "english_name",
        english,
    )


def button_labels(view: discord.ui.View):
    return [item.label for item in view.children]


class Test_部分一致検索:
    async def test_1件だけ一致すればそのまま採用する(self, ctx, result):
        await search(ctx, result, ITEMS, "ネズミ")

        assert result.found[0]["item"] == ITEMS[2]
        assert ctx.replies == []

    async def test_コールバック引数がそのまま渡される(self, ctx, result):
        await search(ctx, result, ITEMS, "ネズミ", arg="SPOILER")

        assert result.found[0]["arg"] == "SPOILER"
        assert result.found[0]["ctx"] is ctx

    async def test_複数一致すれば候補をボタンで表示する(self, ctx, result):
        await search(ctx, result, ITEMS, "グリッド")

        assert result.found == []
        reply = ctx.last_reply
        assert reply["content"] == "候補:"
        assert reply["delete_after"] == 15
        assert button_labels(reply["view"]) == ["グリッド・バグ", "大グリッド・バグ"]

    async def test_完全一致が1件あればそれを採用する(self, ctx, result):
        # 部分一致では2件ヒットするが、完全一致する候補があればそれを選ぶ
        # (コミット bc487eb の回帰テスト)
        await search(ctx, result, ITEMS, "グリッド・バグ")

        assert result.found[0]["item"] == ITEMS[0]
        assert ctx.replies == []


class Test_英語名検索:
    async def test_日本語で一致しなければ英語名で検索する(self, ctx, result):
        await search(ctx, result, ITEMS, "Farmer")

        assert result.found[0]["item"] == ITEMS[3]

    async def test_英語名検索は大文字小文字を区別しない(self, ctx, result):
        await search(ctx, result, ITEMS, "FARMER")

        assert result.found[0]["item"] == ITEMS[3]

    async def test_englishオプションでは日本語名を検索しない(self, ctx, result):
        await search(ctx, result, ITEMS, "ネズミ", english=True)

        # 日本語名では一致しないのであいまい検索に流れる
        assert result.found == []
        assert ctx.last_reply["content"] == "もしかして:"

    async def test_englishオプションのボタンには英語名が並ぶ(self, ctx, result):
        await search(ctx, result, ITEMS, "grid", english=True)

        assert button_labels(ctx.last_reply["view"]) == ["Grid bug", "Giant grid bug"]

    @pytest.mark.parametrize("search_str", ["grid bug", "Grid bug", "GRID BUG"])
    async def test_英語名の完全一致は大文字小文字を区別しない(self, ctx, result, search_str):
        # 部分一致では2件ヒットするが、完全一致する候補があればそれを選ぶ
        await search(ctx, result, ITEMS, search_str, english=True)

        assert result.found[0]["item"] == ITEMS[0]

    async def test_日本語からの英語フォールバックでも完全一致が効く(self, ctx, result):
        # 日本語名で一致せず英語名にフォールバックした場合も、
        # 実際に一致した英語名で完全一致を判定する
        await search(ctx, result, ITEMS, "grid bug")

        assert result.found[0]["item"] == ITEMS[0]

    async def test_英語フォールバックでも候補ボタンは日本語名(self, ctx, result):
        # 完全一致の判定キーが変わっても、表示に使う名前は日本語のままであること
        await search(ctx, result, ITEMS, "giant")

        assert button_labels(ctx.last_reply["view"]) == ["大グリッド・バグ", "大ネズミ"]

    async def test_完全一致しない部分一致は候補表示のまま(self, ctx, result):
        await search(ctx, result, ITEMS, "grid")

        assert result.found == []
        assert len(ctx.last_reply["view"].children) == 2


class Test_候補が多い場合:
    async def test_10件までは候補をボタンで表示する(self, ctx, result):
        items = [{"name": f"モンスター{i}", "english_name": f"mon{i}"} for i in range(10)]

        await search(ctx, result, items, "モンスター")

        assert len(ctx.last_reply["view"].children) == 10

    async def test_11件以上はエラーになる(self, ctx, result):
        items = [{"name": f"モンスター{i}", "english_name": f"mon{i}"} for i in range(11)]

        await search(ctx, result, items, "モンスター")

        assert result.errors == ["候補が多すぎます (11 件)"]
        assert ctx.replies == []


class Test_あいまい検索:
    async def test_一致しなければあいまい候補を表示する(self, ctx, result):
        await search(ctx, result, ITEMS, "存在しない名前")

        reply = ctx.last_reply
        assert reply["content"] == "もしかして:"
        assert reply["delete_after"] == 15
        assert len(reply["view"].children) == len(ITEMS)

    async def test_あいまい候補は最大10件(self, ctx, result):
        items = [{"name": f"名前{i}", "english_name": f"name{i}"} for i in range(30)]

        await search(ctx, result, items, "まったく違う文字列")

        assert len(ctx.last_reply["view"].children) == 10

    async def test_似た名前が上位に来る(self, ctx, result):
        await search(ctx, result, ITEMS, "農夫マゴッド")

        assert ctx.last_reply["view"].children[0].label == "農夫マゴット"


class Test_SelectButton:
    def test_ラベルは80文字までに切り詰められる(self):
        # Discordのボタンラベルは80文字が上限 (コミット 8d63a2d の回帰テスト)
        button = SelectButton({"name": "x"}, "あ" * 100)

        assert len(button.label) == 80
        assert button.label.endswith("...")

    def test_短いラベルはそのまま(self):
        button = SelectButton({"name": "x"}, "グリッド・バグ")

        assert button.label == "グリッド・バグ"

    async def test_長い名前の候補でもボタンを作れる(self, ctx, result):
        items = [
            {"name": "あ" * 200, "english_name": "a" * 200},
            {"name": "あ" * 201, "english_name": "b" * 200},
        ]

        await search(ctx, result, items, "あ")

        assert all(len(label) <= 80 for label in button_labels(ctx.last_reply["view"]))


class FakeInteraction:
    def __init__(self, user_id: int):
        self.user = FakeUser(user_id)
        self.message = FakeInteractionMessage()


class FakeUser:
    def __init__(self, user_id: int):
        self.id = user_id


class FakeInteractionMessage:
    def __init__(self):
        self.deleted = False

    async def delete(self):
        self.deleted = True


class Test_ボタンのコールバック:
    async def test_発言者が押すと選択が確定する(self, ctx, result):
        view = SelectView(ctx, result.on_found, "ARG")
        button = SelectButton(ITEMS[0], ITEMS[0]["name"])
        view.add_item(button)
        interaction = FakeInteraction(ctx.message.author.id)

        await button.callback(interaction)

        assert interaction.message.deleted is True
        assert result.found[0]["item"] == ITEMS[0]
        assert result.found[0]["arg"] == "ARG"

    async def test_発言者以外が押しても何も起きない(self, ctx, result):
        view = SelectView(ctx, result.on_found, "ARG")
        button = SelectButton(ITEMS[0], ITEMS[0]["name"])
        view.add_item(button)
        interaction = FakeInteraction(ctx.message.author.id + 1)

        await button.callback(interaction)

        assert interaction.message.deleted is False
        assert result.found == []

    async def test_ビューに属さないボタンは何もしない(self, ctx, result):
        button = SelectButton(ITEMS[0], ITEMS[0]["name"])
        interaction = FakeInteraction(ctx.message.author.id)

        await button.callback(interaction)

        assert interaction.message.deleted is False
        assert result.found == []
