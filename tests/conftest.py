"""テスト全体で使う共通のfixtureとスタブ

Discordへの接続やネットワークI/Oは一切行わない。
DBは全て pytest の tmp_path 配下に作成する。
"""

import os
import sqlite3
import sys
from typing import Any, cast

import aiohttp
import discord
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ActivationInfoReader  # noqa: E402
import ArtifactInfoReader  # noqa: E402
import FlagInfoReader  # noqa: E402
import KindInfoReader  # noqa: E402
import MonsterInfo  # noqa: E402
import MonsterInfoReader  # noqa: E402

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# リポジトリの実際のflag_info.txt (回帰テストで実データを検証するために使う)
REAL_FLAG_INFO_PATH = FlagInfoReader.FLAG_INFO_PATH


def fixture_path(name: str) -> str:
    """tests/fixtures 配下のファイルパスを返す"""
    return os.path.join(FIXTURES_DIR, name)


def read_fixture(name: str) -> str:
    """tests/fixtures 配下のファイルの内容を返す"""
    with open(fixture_path(name), encoding="utf-8") as f:
        return f.read()


def create_old_schema_flag_info(db_path: str) -> None:
    """source 列が追加される前のスキーマで flag_info テーブルを作る"""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE flag_info("
            "name TEXT PRIMARY KEY, flag_group TEXT,"
            " id_in_group INTEGER, description TEXT)"
        )


@pytest.fixture
def artifact_defs_txt() -> str:
    return read_fixture("ArtifactDefinitions.jsonc")


@pytest.fixture
def baseitem_defs_txt() -> str:
    return read_fixture("BaseitemDefinitions.jsonc")


@pytest.fixture
def activation_table_src() -> str:
    return read_fixture("activation-info-table.cpp")


@pytest.fixture
def spoiler_table_src() -> str:
    return read_fixture("spoiler-table.cpp")


@pytest.fixture
def mon_info_txt() -> str:
    return read_fixture("mon-info.txt")


@pytest.fixture
def art_db(
    tmp_path,
    artifact_defs_txt,
    baseitem_defs_txt,
    activation_table_src,
    spoiler_table_src,
) -> str:
    """アーティファクト情報の全テーブルを作成した一時DBのパスを返す

    flag_info は実際の flag_info.txt と、本家 spoiler-table.cpp の縮小版から作る。
    """
    db_path = str(tmp_path / "art-info-test.db")

    FlagInfoReader.FlagInfoReader().create_flag_info_table(
        db_path, spoiler_table_src, REAL_FLAG_INFO_PATH
    )
    KindInfoReader.KindInfoReader().create_k_info_table(db_path, baseitem_defs_txt)
    ActivationInfoReader.ActivationInfoReader().create_activation_info_table(
        db_path, activation_table_src
    )
    ArtifactInfoReader.ArtifactInfoReader().create_a_info_table(
        db_path, artifact_defs_txt
    )

    return db_path


@pytest.fixture
async def mon_db(tmp_path, mon_info_txt) -> str:
    """モンスター情報を投入した一時DBのパスを返す"""
    import aiosqlite

    db_path = str(tmp_path / "mon-info-test.db")
    m_info = MonsterInfo.MonsterInfo(db_path)
    reader = MonsterInfoReader.MonsterInfoReader()

    async with aiosqlite.connect(db_path) as con:
        await m_info.clear_db(con)
        await con.executemany(
            """
INSERT INTO mon_info VALUES(
    :id, :name, :english_name, :is_unique, :symbol,
    :level, :rarity, :speed, :hp, :ac, :exp, :detail
)
""",
            reader.get_mon_info_list(mon_info_txt),
        )
        await con.commit()

    return db_path


class FakeContext:
    """discord.ext.commands.Context の代わりに使うスタブ

    reply() / send_help() の呼び出し内容を記録するだけで、通信は行わない。
    """

    def __init__(self, author_id: int = 1):
        self.replies: list[dict[str, Any]] = []
        self.help_calls: list[Any] = []
        self.command = object()
        self.message = FakeMessage(author_id)

    async def reply(self, content=None, *, embed=None, view=None, delete_after=None):
        self.replies.append(
            {
                "content": content,
                "embed": embed,
                "view": view,
                "delete_after": delete_after,
            }
        )

    async def send_help(self, command=None):
        self.help_calls.append(command)

    @property
    def last_reply(self) -> dict[str, Any]:
        return self.replies[-1]


class FakeAuthor:
    def __init__(self, author_id: int):
        self.id = author_id


class FakeMessage:
    def __init__(self, author_id: int):
        self.author = FakeAuthor(author_id)


@pytest.fixture
def ctx() -> FakeContext:
    return FakeContext()


class FakeResponse:
    """aiohttp のレスポンスを模したスタブ"""

    def __init__(
        self, status: int = 200, body: str = "", headers: dict[str, str] | None = None
    ):
        self.status = status
        self.body = body
        self.headers = headers if headers is not None else {}

    async def text(self) -> str:
        return self.body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


class FakeClientSession:
    """aiohttp.ClientSession を模したスタブ

    responses は「URLの部分文字列 -> FakeResponse」の辞書。
    値をリストにすると呼び出しごとに先頭から順に返す。
    どのキーにも一致しない場合は status 404 を返す。
    """

    def __init__(
        self,
        responses: dict[str, Any] | FakeResponse | None = None,
        **kwargs,
    ):
        if isinstance(responses, FakeResponse):
            responses = {"": responses}
        self.responses: dict[str, Any] = responses or {}
        self.requests: list[dict[str, Any]] = []
        self.closed = False

    def get(
        self, url: str, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> FakeResponse:
        self.requests.append({"url": url, "headers": headers})
        for key, res in self.responses.items():
            if key in url:
                if isinstance(res, list):
                    return res.pop(0) if res else FakeResponse(status=404)
                return res
        return FakeResponse(status=404)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        self.closed = True
        return False


# --- 型チェック用のキャストヘルパ -------------------------------------------
#
# 上のスタブは本物のクラスを継承していないため、本番コードの引数にそのまま渡すと
# 型エラーになる。本番側のシグネチャは正確なまま保ちたいので、テストの呼び出し側で
# キャストする。実行時には何もしない。


def as_session(session: FakeClientSession) -> aiohttp.ClientSession:
    return cast(aiohttp.ClientSession, session)


# FakeInteraction は test_list_search.py 側で定義されているためここでは Any で受ける
def as_interaction(interaction: Any) -> discord.Interaction:
    return cast(discord.Interaction, interaction)
