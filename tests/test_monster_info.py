"""MonsterInfo のテスト

DBの読み書きと、スポイラー取得〜更新判定の流れを検証する。
HTTP通信は FakeClientSession に差し替えるため実際の通信は行わない。
"""

import hashlib

import aiosqlite
import pytest
from conftest import FakeClientSession, FakeResponse, read_fixture

import MonsterInfo

MON_INFO_URL = "https://example.invalid/mon-info.txt"


def patch_client_session(monkeypatch, session: FakeClientSession) -> None:
    """aiohttp.ClientSession() が常に指定のスタブを返すようにする"""
    monkeypatch.setattr(MonsterInfo.aiohttp, "ClientSession", lambda *a, **kw: session)


class Test_DBの読み出し:
    async def test_モンスター一覧を取得できる(self, mon_db):
        m_info = MonsterInfo.MonsterInfo(mon_db)

        mon_list = await m_info.get_monster_info_list()

        assert [m["id"] for m in mon_list] == [16, 34, 110, 1259]
        assert mon_list[0]["name"] == "グリッド・バグ"

    async def test_一覧には詳細が含まれない(self, mon_db):
        # 詳細は容量が大きいため別途取得する
        m_info = MonsterInfo.MonsterInfo(mon_db)

        mon_list = await m_info.get_monster_info_list()

        assert "detail" not in mon_list[0]

    async def test_詳細を取得できる(self, mon_db):
        m_info = MonsterInfo.MonsterInfo(mon_db)

        detail = await m_info.get_monster_detail(16)

        assert detail.startswith("小さな紫色のピカピカ光る虫だ。")

    async def test_存在しないIDの詳細は空文字(self, mon_db):
        m_info = MonsterInfo.MonsterInfo(mon_db)

        assert await m_info.get_monster_detail(999999) == ""


class Test_clear_db:
    async def test_テーブルが作り直される(self, tmp_path):
        db_path = str(tmp_path / "mon.db")
        m_info = MonsterInfo.MonsterInfo(db_path)

        async with aiosqlite.connect(db_path) as con:
            await m_info.clear_db(con)
            await con.execute(
                "INSERT INTO mon_info VALUES(1,'a','a',0,'x',1,1,0,'1d1',1,1,'d')"
            )
            await con.commit()
            await m_info.clear_db(con)
            async with con.execute("SELECT COUNT(*) FROM mon_info") as c:
                count = (await c.fetchone())[0]

        assert count == 0


class Test_get_current_mon_info_hash:
    async def test_DBが存在しない場合は空文字(self, tmp_path):
        m_info = MonsterInfo.MonsterInfo(str(tmp_path / "not-exist.db"))

        assert await m_info.get_current_mon_info_hash() == ""

    async def test_保存したハッシュを取得できる(self, tmp_path):
        db_path = str(tmp_path / "mon.db")
        m_info = MonsterInfo.MonsterInfo(db_path)

        async with aiosqlite.connect(db_path) as con:
            await m_info.clear_db(con)
            await con.execute(
                "INSERT INTO mon_info_file_hash VALUES(:hash)", {"hash": "abc123"}
            )
            await con.commit()

        assert await m_info.get_current_mon_info_hash() == "abc123"


class Test_check_update:
    @pytest.fixture
    def m_info(self, tmp_path):
        return MonsterInfo.MonsterInfo(str(tmp_path / "mon.db"))

    async def test_更新があればDBに取り込む(self, monkeypatch, m_info):
        body = read_fixture("mon-info.txt")
        session = FakeClientSession(FakeResponse(200, body, {"etag": "W/tag-1"}))
        patch_client_session(monkeypatch, session)

        assert await m_info.check_update(MON_INFO_URL) is True

        mon_list = await m_info.get_monster_info_list()
        assert len(mon_list) == 4

    async def test_レスポンスのetagを保持する(self, monkeypatch, m_info):
        body = read_fixture("mon-info.txt")
        session = FakeClientSession(FakeResponse(200, body, {"etag": "W/tag-1"}))
        patch_client_session(monkeypatch, session)

        await m_info.check_update(MON_INFO_URL)

        assert m_info.etag == "W/tag-1"
        # 次回のリクエストでは if-none-match として送られる
        session2 = FakeClientSession(FakeResponse(304))
        patch_client_session(monkeypatch, session2)
        await m_info.check_update(MON_INFO_URL)
        assert session2.requests[-1]["headers"] == {"if-none-match": "W/tag-1"}

    async def test_ステータスが200以外なら何もしない(self, monkeypatch, m_info):
        session = FakeClientSession(FakeResponse(304))
        patch_client_session(monkeypatch, session)

        assert await m_info.check_update(MON_INFO_URL) is False

    async def test_内容が同じならDBを更新しない(self, monkeypatch, m_info):
        body = read_fixture("mon-info.txt")
        patch_client_session(
            monkeypatch, FakeClientSession(FakeResponse(200, body, {"etag": "t1"}))
        )
        assert await m_info.check_update(MON_INFO_URL) is True

        # etagが変わっても内容が同じならMD5比較で更新をスキップする
        patch_client_session(
            monkeypatch, FakeClientSession(FakeResponse(200, body, {"etag": "t2"}))
        )
        assert await m_info.check_update(MON_INFO_URL) is False

    async def test_内容が変わればDBを更新する(self, monkeypatch, m_info):
        body = read_fixture("mon-info.txt")
        patch_client_session(monkeypatch, FakeClientSession(FakeResponse(200, body)))
        await m_info.check_update(MON_INFO_URL)

        new_body = body + (
            "追加モンスター/Added one (白い 'x')\n"
            "=== Num:2000  Lev:1  Rar:1  Spd:+0  Hp:1d1  Ac:1  Exp:1\n"
            "新しく追加された。\n"
            "\n"
        )
        patch_client_session(
            monkeypatch, FakeClientSession(FakeResponse(200, new_body))
        )

        assert await m_info.check_update(MON_INFO_URL) is True
        mon_list = await m_info.get_monster_info_list()
        assert len(mon_list) == 5

    async def test_取得内容のMD5が保存される(self, monkeypatch, m_info):
        body = read_fixture("mon-info.txt")
        patch_client_session(monkeypatch, FakeClientSession(FakeResponse(200, body)))

        await m_info.check_update(MON_INFO_URL)

        expected = hashlib.md5(body.encode("utf-8")).hexdigest()
        assert await m_info.get_current_mon_info_hash() == expected

    async def test_初回リクエストではetagを送らない(self, monkeypatch, m_info):
        session = FakeClientSession(FakeResponse(304))
        patch_client_session(monkeypatch, session)

        await m_info.check_update(MON_INFO_URL)

        assert session.requests[0]["url"] == MON_INFO_URL
        assert session.requests[0]["headers"] == {"if-none-match": ""}
