import datetime
import json
import os
from logging import getLogger
from operator import attrgetter
from typing import List

import bitlyshortener
import discord
import feedparser
from discord.ext import commands, tasks
from feedparser.util import FeedParserDict


class RssChecker:
    RECORD_DIR = os.path.expanduser('~/.rss_checker')

    def __init__(self, name: str, url: str):
        self.url = url
        os.makedirs(self.RECORD_DIR, exist_ok=True)
        self.record_path = os.path.join(self.RECORD_DIR, name) + '.json'
        self.__load_record()

    def __load_record(self):
        try:
            with open(self.record_path, 'r') as f:
                self.record = json.load(f)
        except FileNotFoundError:
            self.record = {"last_updated_time": 0}

    def __save_record(self):
        with open(self.record_path, 'w') as f:
            json.dump(self.record, f)

    def get_new_items(self) -> List[FeedParserDict]:
        try:
            feed = feedparser.parse(self.url)
        except Exception as e:
            # Feed取得エラー
            getLogger(__name__).warning(e.args)
            return []

        if feed.bozo:
            # Feedパースエラー
            getLogger(__name__).warning(feed.bozo_exception)
            return []

        self.add_last_updated_time(feed)
        new_items = [
            i for i in feed.entries if i.last_updated_time >
            self.record["last_updated_time"]]
        if len(new_items) > 0:
            new_items.sort(key=attrgetter('last_updated_time'), reverse=True)
            self.record["last_updated_time"] = new_items[0].last_updated_time
            self.__save_record()
        return new_items

    def add_last_updated_time(self, d: feedparser.FeedParserDict):
        for i in d.entries:
            i.last_updated_time = datetime.datetime(
                *i.updated_parsed[:6]).timestamp()


class PukiwikiRssChecker(RssChecker):
    def add_last_updated_time(self, d: feedparser.FeedParserDict):
        for i in d.entries:
            i.last_updated_time = datetime.datetime.strptime(
                i.summary, '%a, %d %b %Y %H:%M:%S %Z'
            ).timestamp()


class RssCheckCog(commands.Cog):
    def __init__(self, bot: commands.Bot, config: dict):
        self.checkers = []  # type: List[RssChecker]
        for feed in config["feeds"]:
            checker_class = feed.get("checker", "RssChecker")
            checker = eval(checker_class)(feed["name"], feed["url"])
            checker.name = feed["name"]
            checker.send_channel_id = feed["channel_id"]
            self.checkers.append(checker)

        self.shortener = bitlyshortener.Shortener(
            tokens=config["bitly_tokens"])
        self.bot = bot

        self.checker_task.start()

    def cog_unload(self):
        self.checker_task.cancel()

    @tasks.loop(seconds=60.0)
    async def checker_task(self):
        for checker in self.checkers:
            new_items = checker.get_new_items()[:5]
            if len(new_items) == 0:
                continue

            new_item_links = [getattr(i, 'link') for i in new_items]
            shorten_urls_dict = self.shortener.shorten_urls_to_dict(
                new_item_links)
            channel = self.bot.get_channel(checker.send_channel_id)
            embed = discord.Embed(title=checker.name)
            for i in new_items:
                embed.add_field(
                    name=i.title,
                    value=shorten_urls_dict.get(i.link, "")
                )
            await channel.send(embed=embed)

    @checker_task.before_loop
    async def before_checker_task(self):
        await self.bot.wait_until_ready()


def setup(bot: commands.Bot):
    bot.add_cog(RssCheckCog(bot, bot.ext))
