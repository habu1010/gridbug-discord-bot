"""MonsterSpoiler のテスト

MonsterSpoiler は __init__ で checker_task を起動するため、
__new__ でインスタンスだけ作り必要な属性を差し込んで検証する。
"""

import discord
import pytest

import MonsterInfo
from MonsterSpoiler import MonsterSpoiler

MON_INFO = {
    "id": 16,
    "name": "グリッド・バグ",
    "english_name": "Grid bug",
    "is_unique": 0,
    "symbol": "紫の 'I'",
    "level": 1,
    "rarity": 1,
    "speed": 0,
    "hp": "2d3",
    "ac": 12,
    "exp": 1,
}


@pytest.fixture
def cog(mon_db) -> MonsterSpoiler:
    # __init__ (= checker_task の起動) を回避してインスタンスを作る
    spoiler = MonsterSpoiler.__new__(MonsterSpoiler)
    spoiler.m_info = MonsterInfo.MonsterInfo(mon_db)
    spoiler.mon_info_list = []
    return spoiler


class Test_create_mon_info_embed:
    async def test_タイトルに名前とシンボルが並ぶ(self, cog):
        embed = await cog.create_mon_info_embed(MON_INFO)

        assert embed.title == "グリッド・バグ / Grid bug (紫の 'I')"

    async def test_ユニークには接頭辞が付く(self, cog):
        embed = await cog.create_mon_info_embed(dict(MON_INFO, is_unique=1))

        assert embed.title.startswith("[U] ")

    async def test_説明にステータスと詳細が含まれる(self, cog):
        embed = await cog.create_mon_info_embed(MON_INFO)

        assert "ID:16" in embed.description
        assert "階層:1" in embed.description
        assert "HP:2d3" in embed.description
        assert "小さな紫色のピカピカ光る虫だ。" in embed.description

    async def test_タイトルは256文字に制限される(self, cog):
        # Discord の Embed title は256文字が上限
        long_mon = dict(MON_INFO, name="あ" * 300, id=1259)

        embed = await cog.create_mon_info_embed(long_mon)

        assert len(embed.title) == 256
        assert embed.title.endswith("...")

    async def test_詳細が無いモンスターでも生成できる(self, cog):
        embed = await cog.create_mon_info_embed(dict(MON_INFO, id=999999))

        assert isinstance(embed, discord.Embed)
        assert embed.description.endswith("\n\n")


class Test_send_mon_info:
    async def test_Embedが返信される(self, cog, ctx):
        await cog.send_mon_info(ctx, MON_INFO, None)

        assert ctx.last_reply["embed"].title == "グリッド・バグ / Grid bug (紫の 'I')"


class Test_send_error:
    async def test_赤色のEmbedで返信される(self, cog, ctx):
        await cog.send_error(ctx, "候補が多すぎます (11 件)")

        embed = ctx.last_reply["embed"]
        assert embed.title == "候補が多すぎます (11 件)"
        assert embed.color == discord.Color.red()
