import re
from dataclasses import dataclass
from typing import Any, List


@dataclass
class MonsterInfoReader:
    name_lines: List[str]
    detail_lines: List[str]
    info_line: str

    def __init__(self):
        self.clear()

    def clear(self):
        self.name_lines = []
        self.detail_lines = []
        self.info_line = ""

    def has_complete_data(self):
        return self.name_lines and self.info_line and self.detail_lines

    def push_line(self, line: str):
        if line.startswith("==="):
            self.info_line = line
        elif self.info_line:
            self.detail_lines.append(line)
        else:
            self.name_lines.append(line)

    def get_mon_info_list(self, mon_info: str):
        lines = mon_info.splitlines()

        for line in lines:
            if not line:
                if (result := self.parse()) is not None:
                    yield result
                self.clear()
            else:
                self.push_line(line)

    def parse(self) -> dict[str, Any] | None:
        if not self.has_complete_data():
            return None
        # モンスター名の解析
        name_line = "\n".join(self.name_lines)
        m = re.match(
            r"^(\[.\])?\s*(?:(.+)\/)?(.+)\s*\((.+?)\)$", name_line, flags=re.DOTALL
        )
        if m is None:
            return
        name = m[2].replace("\n", "")
        english_name = m[3].replace("\n", " ")
        is_unique = True if m[1] else False
        symbol = m[4].replace("\n", "")

        # モンスター情報の解析
        m = re.match(
            r"^=== Num:(\d+)  Lev:(\d+)  Rar:(\d+)  Spd:(.+)  Hp:(.+)  Ac:(\d+)  Exp:(\d+)",  # noqa: E501
            self.info_line,
        )
        if m is None:
            return
        result = {
            "id": m[1],
            "name": name,
            "english_name": english_name,
            "is_unique": is_unique,
            "symbol": symbol,
            "level": m[2],
            "rarity": m[3],
            "speed": m[4],
            "hp": m[5],
            "ac": m[6],
            "exp": m[7],
            "detail": "".join(self.detail_lines),
        }
        return result
