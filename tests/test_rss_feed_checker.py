"""RssFeedChecker のテスト

RECORD_DIR を tmp_path に差し替えるため、ホームディレクトリには書き込まない。
RssCheckCog は __init__ で checker_task を起動するためテストでは生成しない。
"""

import datetime
import json
import logging
import os

import feedparser
import pytest
from conftest import FakeClientSession, FakeResponse, as_session

from RssFeedChecker import HengscoreRssChecker, PukiwikiRssChecker, RssChecker

FEED_URL = "https://example.invalid/feed.rss"


def build_rss(items: list) -> str:
    """RSS 2.0 のフィードを組み立てる

    items は (title, link, pubDate) のリスト。
    """
    entries = "".join(
        f"""
    <item>
      <title>{title}</title>
      <link>{link}</link>
      <description>{pub_date}</description>
      <pubDate>{pub_date}</pubDate>
    </item>"""
        for title, link, pub_date in items
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>テストフィード</title>
    <link>https://example.invalid/</link>
    <description>テスト</description>{entries}
  </channel>
</rss>
"""


ITEMS = [
    ("記事1", "https://example.invalid/1", "Mon, 01 Jan 2024 00:00:00 GMT"),
    ("記事2", "https://example.invalid/2", "Tue, 02 Jan 2024 00:00:00 GMT"),
    ("記事3", "https://example.invalid/3", "Wed, 03 Jan 2024 00:00:00 GMT"),
]


@pytest.fixture(autouse=True)
def record_dir(tmp_path, monkeypatch):
    """記録ファイルの保存先を一時ディレクトリに向ける"""
    path = str(tmp_path / "rss_checker")
    monkeypatch.setattr(RssChecker, "RECORD_DIR", path)
    return path


def make_checker(cls=RssChecker, name="test") -> RssChecker:
    checker = cls(name, FEED_URL)
    checker.name = name
    return checker


class Test_記録ファイル:
    def test_記録がなければ0で始まる(self):
        checker = make_checker()

        assert checker.record == {"last_updated_time": 0}

    def test_保存された記録を読み込む(self, record_dir):
        os.makedirs(record_dir, exist_ok=True)
        with open(os.path.join(record_dir, "saved.json"), "w") as f:
            json.dump({"last_updated_time": 12345}, f)

        checker = make_checker(name="saved")

        assert checker.record["last_updated_time"] == 12345


class Test_get_new_items:
    async def test_全件が新着として返る(self):
        checker = make_checker()
        session = FakeClientSession(FakeResponse(200, build_rss(ITEMS)))

        new_items = await checker.get_new_items(as_session(session), 5)

        assert [i.title for i in new_items] == ["記事3", "記事2", "記事1"]

    async def test_新しい順に並ぶ(self):
        checker = make_checker()
        session = FakeClientSession(FakeResponse(200, build_rss(ITEMS)))

        new_items = await checker.get_new_items(as_session(session), 5)

        times = [i.last_updated_time for i in new_items]
        assert times == sorted(times, reverse=True)

    async def test_max件までしか返さない(self):
        checker = make_checker()
        session = FakeClientSession(FakeResponse(200, build_rss(ITEMS)))

        new_items = await checker.get_new_items(as_session(session), 2)

        assert [i.title for i in new_items] == ["記事3", "記事2"]

    async def test_2回目は新着のみ返る(self):
        checker = make_checker()
        session = FakeClientSession(FakeResponse(200, build_rss(ITEMS)))
        await checker.get_new_items(as_session(session), 5)

        new_item = ("記事4", "https://example.invalid/4", "Thu, 04 Jan 2024 00:00:00 GMT")
        session = FakeClientSession(FakeResponse(200, build_rss(ITEMS + [new_item])))
        new_items = await checker.get_new_items(as_session(session), 5)

        assert [i.title for i in new_items] == ["記事4"]

    async def test_更新がなければ空になる(self):
        checker = make_checker()
        session = FakeClientSession(FakeResponse(200, build_rss(ITEMS)))
        await checker.get_new_items(as_session(session), 5)

        new_items = await checker.get_new_items(as_session(session), 5)

        assert new_items == []

    async def test_最終更新時刻が記録ファイルに保存される(self, record_dir):
        checker = make_checker()
        session = FakeClientSession(FakeResponse(200, build_rss(ITEMS)))

        await checker.get_new_items(as_session(session), 5)

        with open(os.path.join(record_dir, "test.json")) as f:
            saved = json.load(f)
        assert saved["last_updated_time"] == checker.record["last_updated_time"]

        # 別インスタンスでも記録を引き継ぐ
        assert make_checker().record == saved

    async def test_ステータスが200以外なら空になる(self):
        checker = make_checker()
        session = FakeClientSession(FakeResponse(404))

        assert await checker.get_new_items(as_session(session), 5) == []

    async def test_パースエラーなら空になり警告が出る(self, caplog):
        checker = make_checker()
        session = FakeClientSession(FakeResponse(200, "<rss><不正なXML>"))

        with caplog.at_level(logging.WARNING):
            new_items = await checker.get_new_items(as_session(session), 5)

        assert new_items == []
        assert caplog.records


def to_timestamp(year, month, day) -> float:
    """実装と同じくローカルタイムとして解釈した場合のタイムスタンプ

    RssChecker はタイムゾーン情報を捨てて naive な datetime にしているため、
    実行環境のタイムゾーンに依存した値になる (更新判定は相対比較のみなので影響はない)。
    """
    return datetime.datetime(year, month, day).timestamp()


class Test_add_last_updated_time:
    def test_pubDateから更新時刻を求める(self):
        checker = make_checker()
        feed = feedparser.parse(build_rss(ITEMS))

        checker.add_last_updated_time(feed)

        assert [i.last_updated_time for i in feed.entries] == [
            to_timestamp(2024, 1, 1),
            to_timestamp(2024, 1, 2),
            to_timestamp(2024, 1, 3),
        ]

    def test_pukiwikiはsummaryから更新時刻を求める(self):
        checker = make_checker(PukiwikiRssChecker)
        feed = feedparser.parse(build_rss(ITEMS))

        checker.add_last_updated_time(feed)

        # description(summary) の日時文字列を解釈する
        assert feed.entries[0].last_updated_time == to_timestamp(2024, 1, 1)

    def test_pukiwikiでsummaryの書式が違えば例外になる(self):
        checker = make_checker(PukiwikiRssChecker)
        feed = feedparser.parse(
            build_rss([("記事", "https://example.invalid/1", "2024/01/01")])
        )

        with pytest.raises(ValueError):
            checker.add_last_updated_time(feed)


class Test_build_embed:
    def test_タイトルとリンクと発信元を設定する(self):
        checker = make_checker(name="変愚蛮怒Wiki")
        feed = feedparser.parse(build_rss(ITEMS))

        embed = checker.build_embed(feed.entries[0])

        assert embed.title == "記事1"
        assert embed.url == "https://example.invalid/1"
        assert embed.author.name == "変愚蛮怒Wiki"

    def test_hengscoreはスクリーンへのリンクを付ける(self):
        checker = make_checker(HengscoreRssChecker, name="Hengscore")
        items = [
            (
                "ダンプ",
                "https://example.invalid/show_dump.php?id=1",
                "Mon, 01 Jan 2024 00:00:00 GMT",
            )
        ]
        feed = feedparser.parse(build_rss(items))

        embed = checker.build_embed(feed.entries[0])

        assert embed.description == (
            ":camera:[screen](https://example.invalid/show_screen.php?id=1)"
        )
        assert embed.url == "https://example.invalid/show_dump.php?id=1"
