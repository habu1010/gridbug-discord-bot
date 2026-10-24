"""RssFeedChecker のテスト

RECORD_DIR を tmp_path に差し替えるため、ホームディレクトリには書き込まない。
RssCheckCog は __init__ で checker_task を起動するため、__new__ で生成して属性を差し込む。
"""

import datetime
import json
import logging
import os
from typing import cast
from xml.sax.saxutils import escape

import discord
import feedparser
import pytest
from conftest import FakeClientSession, FakeResponse, as_session

from RssFeedChecker import (
    HengscoreRssChecker,
    PukiwikiRssChecker,
    RssCheckCog,
    RssChecker,
)

FEED_URL = "https://example.invalid/feed.rss"
CHANNEL_ID = 12345


def build_rss(items: list) -> str:
    """RSS 2.0 のフィードを組み立てる

    items は (title, link, pubDate) のリスト。
    """
    entries = "".join(f"""
    <item>
      <title>{title}</title>
      <link>{link}</link>
      <description>{pub_date}</description>
      <pubDate>{pub_date}</pubDate>
    </item>""" for title, link, pub_date in items)
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
    return cls(name, FEED_URL, CHANNEL_ID)


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

        new_item = (
            "記事4",
            "https://example.invalid/4",
            "Thu, 04 Jan 2024 00:00:00 GMT",
        )
        session = FakeClientSession(FakeResponse(200, build_rss(ITEMS + [new_item])))
        new_items = await checker.get_new_items(as_session(session), 5)

        assert [i.title for i in new_items] == ["記事4"]

    @pytest.mark.parametrize(
        "res_url, expected",
        [
            # リダイレクトされなければフィードのURLが基準
            (None, "https://example.invalid/scores/1/dump"),
            # リダイレクトされたら移転先のURLが基準
            ("https://moved.invalid/feed.rss", "https://moved.invalid/scores/1/dump"),
        ],
    )
    async def test_相対URLのリンクを絶対URLにする(self, res_url, expected):
        checker = make_checker()
        items = [("記事1", "/scores/1/dump", "Mon, 01 Jan 2024 00:00:00 GMT")]
        res = FakeResponse(200, build_rss(items), url=res_url)
        session = FakeClientSession(res)

        new_items = await checker.get_new_items(as_session(session), 5)

        assert new_items[0]["link"] == expected

    # 空のリンクは、フィード自体のURLに解決されないことも確かめる
    @pytest.mark.parametrize("link_elem", ["", "<link></link>"])
    async def test_リンクの無い記事はリンクなしで通知する(self, link_elem):
        checker = make_checker()
        rss = build_rss(ITEMS).replace(
            "<link>https://example.invalid/1</link>", link_elem
        )
        session = FakeClientSession(FakeResponse(200, rss))

        new_items = await checker.get_new_items(as_session(session), 5)

        assert [i.title for i in new_items] == ["記事3", "記事2", "記事1"]
        assert checker.build_embed(new_items[2]).url is None

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

    async def test_hengscoreはスクリーンへのリンクを付ける(self):
        checker = make_checker(HengscoreRssChecker, name="Hengscore")
        items = [("ダンプ", "/scores/1/dump", "Mon, 01 Jan 2024 00:00:00 GMT")]
        session = FakeClientSession(FakeResponse(200, build_rss(items)))
        new_items = await checker.get_new_items(as_session(session), 5)

        embed = checker.build_embed(new_items[0])

        assert embed.url == "https://example.invalid/scores/1/dump"
        assert embed.description == (
            ":camera:[screen](https://example.invalid/scores/1/screen)"
        )

    def test_hengscoreはダンプでないリンクにスクリーンのリンクを付けない(self):
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

        assert embed.description is None


def build_hengscore_embed(title: str, content: str = "") -> discord.Embed:
    """Hengscore と同じ形の Atom フィードの記事1件から Embed を作る"""
    checker = make_checker(HengscoreRssChecker, name="Hengscore")
    atom = f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>{escape(title)}</title>
    <updated>2024-01-01T00:00:00+09:00</updated>
    <link href="https://example.invalid/scores/1/dump"/>
    <content type="text">{escape(content)}</content>
  </entry>
</feed>
"""
    feed = feedparser.parse(atom)
    return checker.build_embed(feed.entries[0])


def fields(embed: discord.Embed) -> list[tuple[str | None, str | None]]:
    return [(f.name, f.value) for f in embed.fields]


class Test_hengscoreのスコア表示:
    def test_勝利したキャラクターはトロフィーを付けて金色で表示する(self):
        embed = build_hengscore_embed(
            "しあわせもののPERFECT VANITY Score:39640485 マーフォーク 剣術家"
            " 勝利の後引退した"
        )

        assert embed.title == "🏆 しあわせもののPERFECT VANITY"
        assert fields(embed) == [
            ("スコア", "39,640,485"),
            ("種族", "マーフォーク"),
            ("職業", "剣術家"),
            ("結果", "勝利の後引退した"),
        ]
        assert embed.color == discord.Color.gold()

    def test_死亡したキャラクターは赤で表示する(self):
        # 死因には空白が含まれることがある
        embed = build_hengscore_embed(
            "しあわせもののPERFECT VANITY Score:6359244 イーク 魔道具術師"
            " 鉄獄の76階で『死神ももえ』 に殺された"
        )

        assert embed.title == "しあわせもののPERFECT VANITY"
        assert fields(embed)[3] == ("結果", "鉄獄の76階で『死神ももえ』 に殺された")
        assert embed.color == discord.Color.red()

    def test_名前と結果のマークダウンの記号はエスケープする(self):
        embed = build_hengscore_embed(
            "ふつうの__x__ Score:0 人間 戦士 鉄獄の1階で*ゴブリン*に殺された"
        )

        assert embed.title == "ふつうの\\_\\_x\\_\\_"
        assert fields(embed)[3] == ("結果", "鉄獄の1階で\\*ゴブリン\\*に殺された")

    def test_勝利でも死亡でもなければ色を付けない(self):
        embed = build_hengscore_embed("ふつうのあ Score:0 人間 戦士 引退した")

        assert fields(embed)[3] == ("結果", "引退した")
        assert embed.color is None

    def test_形式の違うタイトルはそのまま表示する(self):
        embed = build_hengscore_embed("お知らせ")

        assert embed.title == "お知らせ"
        assert embed.fields == []
        assert embed.color is None


class Test_hengscoreの勝利メッセージ:
    VICTORY_TITLE = "コンバットpriest Score:13843047 半巨人 プリースト 勝利の後引退した"

    def test_勝利メッセージを表示する(self):
        # 実際のフィードと同じく、本文は空白で始まる
        embed = build_hengscore_embed(
            self.VICTORY_TITLE,
            "  [*勝利*メッセージ]\n\n  「トラブルで セプクをします ニンジャのせい」",
        )

        assert fields(embed)[-1] == (
            "勝利メッセージ",
            "「トラブルで セプクをします ニンジャのせい」",
        )

    def test_複数行の勝利メッセージは行頭の空白だけを取り除く(self):
        embed = build_hengscore_embed(
            self.VICTORY_TITLE, "[*勝利*メッセージ]\n\n  1行目\n    2行目\n"
        )

        assert fields(embed)[-1] == ("勝利メッセージ", "1行目\n  2行目")

    def test_マークダウンの記号はエスケープする(self):
        embed = build_hengscore_embed(
            self.VICTORY_TITLE, "[*勝利*メッセージ]\n\n  **強い**"
        )

        assert fields(embed)[-1] == ("勝利メッセージ", "\\*\\*強い\\*\\*")

    def test_長い勝利メッセージはエスケープしても1024文字に収まるよう切り詰める(self):
        embed = build_hengscore_embed(
            self.VICTORY_TITLE, "[*勝利*メッセージ]\n\n  " + "*" * 2000
        )

        assert fields(embed)[-1][1] == "\\*" * 509 + "..."

    @pytest.mark.parametrize(
        "content",
        [
            # 勝利メッセージを書かずに引退した
            "",
            # 死亡したキャラクターの本文は表示しない
            "[死ぬ直前のメッセージ]\n\n> グレムリンに殺された。",
        ],
    )
    def test_勝利メッセージでなければ表示しない(self, content):
        embed = build_hengscore_embed(self.VICTORY_TITLE, content)

        assert "勝利メッセージ" not in [name for name, _ in fields(embed)]


class FakeChannel:
    """送信した Embed を記録するチャンネルのスタブ

    fail_titles に含まれるタイトルの Embed は送信に失敗させる。
    """

    def __init__(self, fail_titles: tuple[str, ...] = ()):
        self.fail_titles = fail_titles
        self.sent: list[str | None] = []

    async def send(self, embed):
        if embed.title in self.fail_titles:
            raise RuntimeError("送信失敗")
        self.sent.append(embed.title)


class Test_checker_task:
    async def test_送信に失敗した記事があっても残りの記事を送る(self, caplog):
        checker = make_checker(name="失敗あり")
        channel = FakeChannel(fail_titles=("記事2",))
        cog = RssCheckCog.__new__(RssCheckCog)
        cog.client_session = as_session(
            FakeClientSession(FakeResponse(200, build_rss(ITEMS)))
        )
        cog.targets = [(checker, cast(discord.abc.Messageable, channel))]

        with caplog.at_level(logging.ERROR):
            await RssCheckCog.checker_task.coro(cog)

        assert channel.sent == ["記事3", "記事1"]
        assert "失敗あり: 記事を送信できませんでした (記事2)" in caplog.text
