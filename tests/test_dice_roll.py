"""DiceRoll のテスト

乱数は random.Random(seed) に差し替えて結果を固定する。
"""

import random
from typing import Any, cast

import discord
import pytest

from DiceRoll import DiceRoll


@pytest.fixture
def cog() -> DiceRoll:
    dice_roll = DiceRoll()
    dice_roll.rng = random.Random(0)
    return dice_roll


def roll(cog: DiceRoll, dice: int, side: int) -> discord.Embed:
    return cog._roll(dice, side)


async def invoke_roll(cog: DiceRoll, ctx: Any, arg: str) -> None:
    """$roll コマンドの本体を直接呼ぶ

    Command.callback は「Cogのメソッド」と「単独の関数」のunionとして
    型付けされており、cog を渡す呼び出しが型エラーになるため cast で落とす。
    """
    await cast(Any, DiceRoll.roll.callback)(cog, ctx, arg)


class Test_diceroll_pattern:
    @pytest.mark.parametrize(
        ("arg", "expected"),
        [
            ("2d6", ("2", "6")),
            ("2D6", ("2", "6")),
            ("100d100", ("100", "100")),
        ],
    )
    def test_一致する書式(self, cog, arg, expected):
        m = cog.diceroll_pattern.match(arg)

        assert m is not None
        assert m.groups() == expected

    @pytest.mark.parametrize("arg", ["d6", "2d", "2x6", "2d6d6", "abc", "", " 2d6"])
    def test_一致しない書式(self, cog, arg):
        assert cog.diceroll_pattern.match(arg) is None


class Test_roll:
    def test_合計と内訳を返す(self, cog):
        # cog.rng と同じ種から同じ手順で期待値を作る
        rng = random.Random(0)
        expected = [rng.randint(1, 6) for _ in range(3)]

        embed = roll(cog, 3, 6)

        # Embed の title は文字列に変換される
        assert embed.title == str(sum(expected))
        assert embed.description == "[" + ",".join(str(i) for i in expected) + "]"

    def test_出目は1から面数の範囲に収まる(self, cog):
        embed = roll(cog, 100, 6)

        assert embed.description is not None
        values = [int(v) for v in embed.description.strip("[]").split(",")]
        assert len(values) == 100
        assert all(1 <= v <= 6 for v in values)

    def test_1面のダイスは必ず1(self, cog):
        embed = roll(cog, 5, 1)

        assert embed.title == "5"
        assert embed.description == "[1,1,1,1,1]"

    def test_100回までは振れる(self, cog):
        embed = roll(cog, 100, 6)

        assert embed.title != "振る回数が多すぎます"

    def test_101回以上はエラーになる(self, cog):
        embed = roll(cog, 101, 6)

        assert embed.title == "振る回数が多すぎます"
        assert embed.color == discord.Color.red()


class Test_rollコマンド:
    async def test_結果が返信される(self, cog, ctx):
        await invoke_roll(cog, ctx, "2d6")

        embed = ctx.last_reply["embed"]
        assert embed.title.isdigit()
        assert 2 <= int(embed.title) <= 12

    @pytest.mark.parametrize("arg", ["abc", "0d6", "2d0"])
    async def test_不正な指定では返信しない(self, cog, ctx, arg):
        await invoke_roll(cog, ctx, arg)

        assert ctx.replies == []

    async def test_振る回数が多すぎる場合はエラーが返信される(self, cog, ctx):
        await invoke_roll(cog, ctx, "101d6")

        assert ctx.last_reply["embed"].title == "振る回数が多すぎます"
