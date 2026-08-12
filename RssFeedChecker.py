import asyncio
import datetime
import json
import os
import time
from logging import getLogger
from operator import itemgetter
from typing import TYPE_CHECKING, Any, cast

import aiohttp
import discord
import feedparser
from discord.ext import commands, tasks
from feedparser.util import FeedParserDict

if TYPE_CHECKING:
    from bot import Bot


class RssChecker:
    RECORD_DIR = os.path.expanduser("~/.rss_checker")

    #: 通知先のチャンネルID。RssCheckCog が設定から読んで代入する。
    send_channel_id: int

    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        os.makedirs(self.RECORD_DIR, exist_ok=True)
        self.record_path = os.path.join(self.RECORD_DIR, name) + ".json"
        self.__load_record()

    def __load_record(self) -> None:
        try:
            with open(self.record_path, "r") as f:
                self.record: dict[str, Any] = json.load(f)
        except FileNotFoundError:
            self.record = {"last_updated_time": 0}

    def __save_record(self) -> None:
        with open(self.record_path, "w") as f:
            json.dump(self.record, f)

    async def get_new_items(
        self, cs: aiohttp.ClientSession, max: int
    ) -> list[FeedParserDict]:
        async with cs.get(self.url) as res:
            if res.status != 200:
                return []
            body = await res.text()

        try:
            feed = feedparser.parse(body)
        except Exception as e:
            # Feed取得エラー
            getLogger(__name__).warning(e.args)
            return []

        if feed.bozo:
            # Feedパースエラー
            getLogger(__name__).warning(feed.bozo_exception)
            return []

        self.add_last_updated_time(feed)
        # FeedParserDict は dict のサブクラスで属性アクセスは型情報を持たないため、
        # 添字アクセスで扱う (実行時の挙動は属性アクセスと同じ)
        new_items: list[FeedParserDict] = [
            i
            for i in feed.entries
            if i["last_updated_time"] > self.record["last_updated_time"]
        ]
        if len(new_items) > 0:
            new_items.sort(key=itemgetter("last_updated_time"), reverse=True)
            self.record["last_updated_time"] = new_items[0]["last_updated_time"]
            self.__save_record()
        return new_items[:max]

    def add_last_updated_time(self, d: FeedParserDict) -> None:
        for i in d.entries:
            updated = cast(time.struct_time, i["updated_parsed"])
            i["last_updated_time"] = datetime.datetime(*updated[:6]).timestamp()

    def build_embed(self, item: FeedParserDict) -> discord.Embed:
        embed = discord.Embed(title=item["title"], url=item["link"])
        embed.set_author(name=self.name)
        return embed


class PukiwikiRssChecker(RssChecker):
    def add_last_updated_time(self, d: FeedParserDict) -> None:
        for i in d.entries:
            summary = cast(str, i["summary"])
            i["last_updated_time"] = datetime.datetime.strptime(
                summary, "%a, %d %b %Y %H:%M:%S %Z"
            ).timestamp()


class HengscoreRssChecker(RssChecker):
    def build_embed(self, item: FeedParserDict) -> discord.Embed:
        embed = super().build_embed(item)
        link = cast(str, item["link"])
        screen_url = link.replace("show_dump.php?", "show_screen.php?")
        embed.description = f":camera:[screen]({screen_url})"
        return embed


class RssCheckCog(commands.Cog):
    #: 設定の checker: に書ける名前とクラスの対応
    CHECKER_CLASSES: dict[str, type[RssChecker]] = {
        c.__name__: c for c in (RssChecker, PukiwikiRssChecker, HengscoreRssChecker)
    }

    def __init__(self, bot: commands.Bot, config: dict[str, Any]):
        self.checkers: list[RssChecker] = []
        for feed in config["feeds"]:
            checker_class_name = feed.get("checker", "RssChecker")
            checker_class = self.CHECKER_CLASSES.get(checker_class_name)
            if checker_class is None:
                getLogger(__name__).warning(
                    f"Unknown RSS checker class: {checker_class_name}"
                )
                continue
            checker = checker_class(feed["name"], feed["url"])
            checker.send_channel_id = feed["channel_id"]
            self.checkers.append(checker)

        self.client_session = aiohttp.ClientSession()
        self.bot = bot

        self.checker_task.start()

    async def cog_unload(self) -> None:
        self.checker_task.cancel()
        await self.client_session.close()

    @tasks.loop(seconds=60.0)
    async def checker_task(self) -> None:
        new_items_list = await asyncio.gather(
            *[c.get_new_items(self.client_session, 5) for c, _ in self.targets]
        )

        for (checker, channel), new_items in zip(self.targets, new_items_list):
            for item in new_items:
                await channel.send(embed=checker.build_embed(item))

    @checker_task.before_loop
    async def before_checker_task(self) -> None:
        await self.bot.wait_until_ready()

        # get_new_items() は取得した記事を既読として記録するため、
        # 送信できないチェッカーはフィードの取得自体を行わないよう最初に除外する
        self.targets: list[tuple[RssChecker, discord.abc.Messageable]] = []
        for checker in self.checkers:
            channel = self.bot.get_channel(checker.send_channel_id)
            if not isinstance(channel, discord.abc.Messageable):
                getLogger(__name__).warning(
                    f"{checker.name}: 送信先チャンネル"
                    f" (id={checker.send_channel_id}) に送信できません"
                )
                continue
            self.targets.append((checker, channel))


async def setup(bot: "Bot") -> None:
    await bot.add_cog(RssCheckCog(bot, bot.ext))
