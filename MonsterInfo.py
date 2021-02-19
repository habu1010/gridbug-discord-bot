import hashlib
import sqlite3
from typing import List

import requests

import MonsterInfoReader


class MonsterInfo:
    """モンスター情報クラス
    """

    def __init__(self, db_path: str):
        """モンスター情報クラスのインスタンスを生成する

        Args:
            db_path (str): モンスター情報を格納するDBのパス
        """
        self.db_path = db_path

    def get_monster_info_list(self) -> List[dict]:
        """モンスター情報のリストを取得する

        モンスターのID、日本語名/英語名、ユニークかどうか、シンボル、
        出現階層、レア度、速度、HP、AC、経験値のリストを取得する

        モンスター詳細は容量が大きいため、別途 get_monster_detail() で取得する

        Returns:
            List[dict]: モンスター情報のリスト
        """

        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.row_factory = sqlite3.Row
            c.execute(
                '''
SELECT id, name, english_name, is_unique, symbol, level, rarity, speed, hp, ac, exp
    FROM mon_info
'''
            )
            mon_info_list = c.fetchall()

        return mon_info_list

    def get_monster_detail(self, monster_id: int) -> str:
        """モンスターの詳細情報を取得する

        Args:
            monster_id (int): モンスターのID

        Returns:
            str: モンスターの詳細情報を表した文字列
        """

        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT detail FROM mon_info WHERE id = :id",
                {"id": monster_id})
            detail = c.fetchone()
        return detail[0] if detail else ""

    def clear_db(self, con: sqlite3.Connection) -> None:
        con.execute('DROP TABLE IF EXISTS mon_info_file_hash')
        con.execute('CREATE TABLE mon_info_file_hash(hash TEXT)')
        con.execute('DROP TABLE IF EXISTS mon_info')
        con.execute(
            '''
CREATE TABLE mon_info(
    id INTEGER PRIMARY KEY,
    name TEXT,
    english_name TEXT,
    is_unique INTEGER,
    symbol TEXT,
    level INTEGER,
    rarity INTEGER,
    speed INTEGER,
    hp TEXT,
    ac INTEGER,
    exp INTEGER,
    detail TEXT
)
'''
        )

    def get_current_mon_info_hash(self) -> str:
        """現在保持しているモンスター情報のハッシュ値を返す

        Returns:
            str: 現在保持しているモンスター情報のハッシュ値
        """
        try:
            with sqlite3.connect(self.db_path) as con:
                c = con.cursor()
                c.row_factory = sqlite3.Row
                c.execute('SELECT hash FROM mon_info_file_hash')
                row = c.fetchall()
        except Exception:
            return ""

        return row[0]['hash'] if len(row) > 0 else ""

    def check_update(self, mon_info_txt_url: str) -> bool:
        """URLからモンスター詳細スポイラーを取得して、必要ならばDBを更新する

        Args:
            mon_info_txt_url (str): モンスター情報スポイラーのURL

        Returns:
            bool: 更新があった場合True、更新が無かった場合False
        """

        # モンスター詳細スポイラーを指定URLからダウンロード
        res = requests.get(mon_info_txt_url)
        if res.status_code != requests.codes.ok:
            return False

        # mon-info.txtのMD5キャッシュを計算し、
        # 保持している内容と同じであれば更新は行わない
        mon_info = res.text
        md5_hash = hashlib.md5(mon_info.encode("utf-8")).hexdigest()
        latest_hash = self.get_current_mon_info_hash()
        if md5_hash == latest_hash:
            return False

        # DBを更新
        m = MonsterInfoReader.MonsterInfoReader()
        with sqlite3.connect(self.db_path) as con:
            self.clear_db(con)
            c = con.cursor()
            c.executemany(
                '''
INSERT INTO mon_info VALUES(
:id, :name, :english_name, :is_unique, :symbol, :level, :rarity, :speed, :hp, :ac, :exp, :detail
)
''',
                m.get_mon_info_list(mon_info)
            )
            c.execute("INSERT INTO mon_info_file_hash VALUES(:hash)", {'hash': md5_hash})

        return True
