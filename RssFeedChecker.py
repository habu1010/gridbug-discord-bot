import asyncio
import datetime
import json
import os
import re
import textwrap
import time
from logging import getLogger
from operator import itemgetter
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urljoin

import aiohttp
import discord
import feedparser
from discord.ext import commands, tasks
from feedparser.util import FeedParserDict

from utils import (
    MAX_EMBED_FIELD_VALUE_LENGTH,
    MAX_EMBED_TITLE_LENGTH,
    limit_str_length,
)

if TYPE_CHECKING:
    from bot import Bot


class RssChecker:
    RECORD_DIR = os.path.expanduser("~/.rss_checker")
    # 問題がこの回数続いたら報告する。一瞬の障害 (通信の瞬断など) は報告せず、
    # 次の確認で取り直す
    REPORT_AFTER_REPEATS = 2

    def __init__(self, name: str, url: str, send_channel_id: int):
        self.name = name
        self.url = url
        self.send_channel_id = send_channel_id
        os.makedirs(self.RECORD_DIR, exist_ok=True)
        self.record_path = os.path.join(self.RECORD_DIR, name) + ".json"
        self.__load_record()
        # 直前に報告した問題の種類 (報告していなければ None) と、それとは別の種類の
        # 問題が続いている回数
        self.last_problem: str | None = None
        self.repeats = 0
        # 直前の確認で更新日時を読めずに読み飛ばした記事の数
        self.last_skipped = 0

    def __load_record(self) -> None:
        try:
            with open(self.record_path, "r") as f:
                self.record: dict[str, Any] = json.load(f)
        except FileNotFoundError:
            self.record = {"last_updated_time": 0}

    def __save_record(self) -> None:
        with open(self.record_path, "w") as f:
            json.dump(self.record, f)

    def report_problem(self, problem: str, detail: str, exc_info: bool = False) -> None:
        """フィードの問題をログに出す

        フィードは毎分確認し、ログは ChannelLogger 経由で Discord にも流れるため、
        直前に報告したのと同じ種類 (problem) の問題は、詳細 (detail) が違っても
        繰り返し出さない。別の種類の問題は REPORT_AFTER_REPEATS 回続くまで出さない。
        """
        if problem == self.last_problem:
            self.repeats = 0
            return
        self.repeats += 1
        if self.repeats < self.REPORT_AFTER_REPEATS:
            return
        getLogger(__name__).warning(
            f"{self.name}: {problem} ({detail})", exc_info=exc_info
        )
        self.last_problem = problem
        self.repeats = 0

    def report_ok(self) -> None:
        """フィードを問題なく確認できたことを記録し、問題が続いていた場合は復旧をログに出す"""
        if self.last_problem is not None:
            getLogger(__name__).warning(f"{self.name}: 復旧しました")
        self.last_problem = None
        self.repeats = 0

    async def get_new_items(
        self, cs: aiohttp.ClientSession, max: int
    ) -> list[FeedParserDict]:
        async with cs.get(self.url) as res:
            if res.status != 200:
                self.report_problem("フィードを取得できません", f"HTTP {res.status}")
                return []
            body = await res.text()
            # リダイレクトされた場合は移転先のURLになる
            base_url = str(res.url)

        try:
            feed = feedparser.parse(body)
        except Exception as e:
            self.report_problem("フィードを解析できません", repr(e))
            return []

        if feed.bozo:
            # XML の解析エラーの位置 (行・桁) は str() にしか含まれない
            e = feed.bozo_exception
            self.report_problem("フィードを解析できません", f"{type(e).__name__}: {e}")
            return []

        # リンクが相対URLのフィード (新しいHengscoreなど) もあるため、
        # フィードのURLを基準に絶対URLにする (Embed の url は http/https しか受け付けない)
        for i in feed.entries:
            if i.get("link"):
                i["link"] = urljoin(base_url, cast(str, i["link"]))

        dated_items = self.add_last_updated_time(feed)
        skipped = len(feed.entries) - len(dated_items)
        # FeedParserDict は dict のサブクラスで属性アクセスは型情報を持たないため、
        # 添字アクセスで扱う (実行時の挙動は属性アクセスと同じ)
        new_items = [
            i
            for i in dated_items
            if i["last_updated_time"] > self.record["last_updated_time"]
        ]
        if len(new_items) > 0:
            new_items.sort(key=itemgetter("last_updated_time"), reverse=True)
            self.record["last_updated_time"] = new_items[0]["last_updated_time"]
            self.__save_record()

        self.report_ok()
        # 読み飛ばしはフィードの取得の問題とは別に、件数が変わった時だけ報告する
        # (日付の無い記事が残り続けても、取得の問題の復旧が分かるように)
        if skipped > 0 and skipped != self.last_skipped:
            getLogger(__name__).warning(
                f"{self.name}: 更新日時を読めない記事を {skipped} 件読み飛ばしました"
            )
        self.last_skipped = skipped
        return new_items[:max]

    def add_last_updated_time(self, d: FeedParserDict) -> list[FeedParserDict]:
        """各記事に更新時刻 (last_updated_time) を付ける

        更新日時を読めない記事は、フィード全体を捨てずにその記事だけを読み飛ばす
        (last_updated_time を付けない)。

        Returns:
            更新時刻を付けられた記事のリスト
        """
        dated_items: list[FeedParserDict] = []
        for i in d.entries:
            try:
                i["last_updated_time"] = self.get_updated_time(i)
            except (KeyError, TypeError, ValueError, OverflowError, OSError):
                # OverflowError / OSError は timestamp() が範囲外の日付で出す
                continue
            dated_items.append(i)
        return dated_items

    def get_updated_time(self, entry: FeedParserDict) -> float:
        updated = cast(time.struct_time, entry["updated_parsed"])
        return datetime.datetime(*updated[:6]).timestamp()

    def build_embed(self, item: FeedParserDict) -> discord.Embed:
        # link の無い (または空の) 記事は、リンクなしで通知する
        embed = discord.Embed(
            title=limit_str_length(cast(str, item["title"]), MAX_EMBED_TITLE_LENGTH),
            url=item.get("link") or None,
        )
        embed.set_author(name=self.name)
        return embed


class PukiwikiRssChecker(RssChecker):
    def get_updated_time(self, entry: FeedParserDict) -> float:
        summary = cast(str, entry["summary"])
        return datetime.datetime.strptime(
            summary, "%a, %d %b %Y %H:%M:%S %Z"
        ).timestamp()


class HengscoreRssChecker(RssChecker):
    # 記事のタイトルの形式: "<性格><名前> Score:<スコア> <種族> <職業> <結果>"
    # 名前と結果 (死因など) には空白が含まれることがある
    TITLE_PATTERN = re.compile(
        r"(?P<name>.+) Score:(?P<score>\d+) (?P<race>\S+) (?P<class>\S+) (?P<result>.+)"
    )
    # 記事の本文の先頭の見出し。勝利したキャラクターでは、この後に勝利メッセージが続く
    # (死亡したキャラクターの本文は死ぬ直前のメッセージで、長いので表示しない)
    VICTORY_MESSAGE_HEADER = "[*勝利*メッセージ]"
    # 勝利メッセージの表示の上限。マークダウンのエスケープで最大2倍の長さになるため、
    # Embed のフィールドの値の上限の半分で切り詰めてからエスケープする
    MAX_VICTORY_MESSAGE_LENGTH = MAX_EMBED_FIELD_VALUE_LENGTH // 2

    def build_embed(self, item: FeedParserDict) -> discord.Embed:
        embed = super().build_embed(item)
        self.add_score_fields(embed, cast(str, item["title"]))
        self.add_victory_message(embed, item)
        link = cast(str, item.get("link", ""))
        # ダンプ (/scores/<id>/dump) と同じ階層にスクリーン (/scores/<id>/screen) がある。
        # 想定と違う形のリンクでは、存在しないページを指さないようスクリーンのリンクを付けない
        if link.endswith("/dump"):
            screen_url = link.removesuffix("/dump") + "/screen"
            embed.description = f":camera:[screen]({screen_url})"
        return embed

    def add_score_fields(self, embed: discord.Embed, title: str) -> None:
        """タイトルを分解して、名前をタイトルに、スコアなどをフィールドに並べる

        想定と違う形式のタイトルは、そのままにする。
        """
        m = self.TITLE_PATTERN.fullmatch(title)
        if m is None:
            return

        # 名前はプレイヤーが自由に付けるので、マークダウンの記号をエスケープする
        name = discord.utils.escape_markdown(m["name"])
        result = m["result"]
        victory = result.startswith("勝利")
        # 帯の色だけでは目立たないので、勝利したキャラクターはタイトルにもトロフィーを付ける
        embed.title = f"🏆 {name}" if victory else name
        embed.add_field(name="スコア", value=f"{int(m['score']):,}")
        embed.add_field(name="種族", value=m["race"])
        embed.add_field(name="職業", value=m["class"])
        embed.add_field(
            name="結果", value=discord.utils.escape_markdown(result), inline=False
        )
        if victory:
            embed.color = discord.Color.gold()
        elif result.endswith("殺された"):
            embed.color = discord.Color.red()

    def add_victory_message(self, embed: discord.Embed, item: FeedParserDict) -> None:
        """本文が勝利メッセージなら、フィールドに表示する"""
        contents = cast(list[FeedParserDict], item.get("content", []))
        if not contents:
            return
        # 実際のフィードの本文は空白で始まる (feedparser が取り除くが、それに頼らない)
        body = cast(str, contents[0]["value"]).lstrip()
        if not body.startswith(self.VICTORY_MESSAGE_HEADER):
            return

        # 本文はインデントされているので、行頭の共通の空白を取り除く
        message = textwrap.dedent(body.removeprefix(self.VICTORY_MESSAGE_HEADER))
        message = message.strip()
        if not message:
            return
        embed.add_field(
            name="勝利メッセージ",
            value=discord.utils.escape_markdown(
                limit_str_length(message, self.MAX_VICTORY_MESSAGE_LENGTH)
            ),
            inline=False,
        )


class RssCheckCog(commands.Cog):
    # 設定の checker: に書ける名前とクラスの対応
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
            self.checkers.append(
                checker_class(feed["name"], feed["url"], feed["channel_id"])
            )

        # 応答しないフィードが1つあると、gather で待つ他のフィードの通知まで遅れるので、
        # aiohttp の既定 (300秒) より短く打ち切る
        self.client_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        self.bot = bot

        self.checker_task.start()

    async def cog_unload(self) -> None:
        self.checker_task.cancel()
        await self.client_session.close()

    @tasks.loop(seconds=60.0)
    async def checker_task(self) -> None:
        await asyncio.gather(
            *[self.check_feed(checker, channel) for checker, channel in self.targets]
        )

    async def check_feed(
        self, checker: RssChecker, channel: discord.abc.Messageable
    ) -> None:
        """1つのフィードの新着を確認して送信する

        失敗してもタスクごと止まって全フィードの通知が途絶えないよう、
        フィードごと・記事ごとに例外を捕まえてログに残す。
        """
        try:
            new_items = await checker.get_new_items(self.client_session, 5)
        except Exception as e:
            checker.report_problem(
                # str() だと TimeoutError などはメッセージが空になるので repr で出す
                "フィードを確認できません",
                repr(e),
                exc_info=True,
            )
            return

        for item in new_items:
            try:
                await channel.send(embed=checker.build_embed(item))
            except Exception:
                getLogger(__name__).exception(
                    f"{checker.name}: 記事を送信できませんでした"
                    f" ({item.get('title')})"
                )

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
