import os
import re
import sqlite3
from collections import Counter
from collections.abc import Iterator
from logging import getLogger
from typing import Any

# 本家 spoiler-table.cpp のテーブル名 -> 表示グループ
# ここに無いテーブル名のフラグは MISC として扱う
SPOILER_TABLE_GROUPS = {
    "stat_flags_desc": "BONUS",
    "pval_flags1_desc": "BONUS",
    "slay_flags_desc": "SLAYING",
    "brand_flags_desc": "BRAND",
    "resist_flags_desc": "RESISTANCE",
    "vulnerable_flags_desc": "VULNERABILITY",
    "immune_flags_desc": "IMMUNITY",
    "sustain_flags_desc": "SUSTAIN_STATUS",
    "misc_flags2_desc": "MISC",
    "misc_flags3_desc": "MISC",
}

# 本家テーブルに無いフラグの表示名と表示グループの定義
FLAG_INFO_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "flag_info.txt"
)

# flag_info テーブルの source 列の値 (各フラグの定義の取得元)
SOURCE_SPOILER_TABLE = "spoiler-table.cpp"
SOURCE_FLAG_INFO_TXT = "flag_info.txt"

SPOILER_TABLE_PATTERN = re.compile(r"(\w+)\s*=\s*\{(.*?)\};", re.DOTALL)
SPOILER_ENTRY_PATTERN = re.compile(
    r'\{\s*TR_(\w+)\s*,\s*_\(\s*"([^"]*)"\s*,\s*"([^"]*)"\s*\)\s*\}'
)


class FlagInfoReader:

    def get_flag_groups(self, flag_info_path: str) -> Iterator[dict[str, Any]]:
        with open(flag_info_path) as f:
            lines = [line.strip() for line in f.readlines()]

        flag_group: dict[str, Any] = dict()
        for line in lines:
            if line.startswith("#"):
                continue
            if line.startswith("$GROUP_START"):
                cols = line.split(":")
                # グループ毎に辞書を作り直す (yield した辞書を呼び出し側が
                # 保持しても、後続のグループの内容で上書きされないようにする)
                flag_group = {
                    "name": cols[1],
                    "description": cols[2],
                    "flags": [],
                }
            elif line.startswith("$GROUP_END"):
                yield flag_group
            else:
                cols = line.split(":")
                if len(cols) == 2:
                    flag_group["flags"].append(
                        {"name": cols[0], "description": cols[1]}
                    )

    def get_spoiler_table_flags(self, src: str) -> Iterator[dict[str, str]]:
        """本家 spoiler-table.cpp からフラグの日本語名と表示グループを取り出す

        `{ TR_XXX, _("日本語", "English") }` 形式のエントリを持つテーブルが対象。
        """
        # コメントアウトされたエントリを拾わないようにコメントを除去する
        src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
        src = re.sub(r"//.*", "", src)

        for table in SPOILER_TABLE_PATTERN.finditer(src):
            group = SPOILER_TABLE_GROUPS.get(table[1], "MISC")
            for entry in SPOILER_ENTRY_PATTERN.finditer(table[2]):
                yield {"name": entry[1], "flag_group": group, "description": entry[2]}

    def has_current_flag_info_table(self, db_path: str) -> bool:
        """現在のスキーマ (source 列あり) の flag_info テーブルがあるかを返す"""
        with sqlite3.connect(db_path) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(flag_info)")}
        return "source" in columns

    def create_flag_info_table(
        self,
        db_path: str,
        spoiler_table_src: str = "",
        flag_info_path: str = FLAG_INFO_PATH,
    ) -> None:
        spoiler_flags = list(self.get_spoiler_table_flags(spoiler_table_src))
        if spoiler_table_src and not spoiler_flags:
            # 本家の書式変更などで読めなかった場合は、本家の定義を含む
            # 既存のテーブルを残す
            getLogger(__name__).warning(
                "spoiler-table.cpp からフラグ定義を取得できませんでした"
            )
            return

        # 本家テーブル -> flag_info.txt の順に、先に出てきた定義を採用する
        # (本家を優先し、本家の複数のテーブルに載っている場合は最初のもの)
        merged: dict[str, tuple[str, str, str]] = {}
        for flag in spoiler_flags:
            merged.setdefault(
                flag["name"],
                (flag["flag_group"], flag["description"], SOURCE_SPOILER_TABLE),
            )
        for flag_group in self.get_flag_groups(flag_info_path):
            for flag in flag_group["flags"]:
                merged.setdefault(
                    flag["name"],
                    (flag_group["name"], flag["description"], SOURCE_FLAG_INFO_TXT),
                )

        # グループ内の並び順は上記の採用順
        id_in_group: Counter[str] = Counter()
        rows = []
        for name, (group, description, source) in merged.items():
            id_in_group[group] += 1
            rows.append((name, group, id_in_group[group], description, source))

        with sqlite3.connect(db_path) as conn:
            conn.execute("DROP TABLE IF EXISTS flag_info")
            conn.execute("""
CREATE TABLE flag_info(
    name TEXT PRIMARY KEY,
    flag_group TEXT,
    id_in_group INTEGER,
    description TEXT,
    source TEXT
)
""")
            conn.executemany("INSERT INTO flag_info VALUES(?, ?, ?, ?, ?)", rows)
