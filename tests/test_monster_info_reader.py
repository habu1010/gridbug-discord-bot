"""MonsterInfoReader のテスト

モンスタースポイラーは「名前行 → '===' で始まる情報行 → 詳細行」を
空行で区切ったプレーンテキスト形式。
"""

from typing import Any

from MonsterInfoReader import MonsterInfoReader

SIMPLE_ENTRY = """グリッド・バグ/Grid bug (紫の 'I')
=== Num:16  Lev:1  Rar:1  Spd:+0  Hp:2d3  Ac:12  Exp:1
小さな紫色のピカピカ光る虫だ。
"""


def parse_raw(text: str) -> dict[str, Any] | None:
    """1体分のテキストを渡してパース結果をそのまま返す (解析失敗ならNone)"""
    reader = MonsterInfoReader()
    for line in text.splitlines():
        reader.push_line(line)
    return reader.parse()


def parse_one(text: str) -> dict[str, Any]:
    """1体分のテキストを渡してパースに成功した結果を返す"""
    result = parse_raw(text)
    assert result is not None
    return result


class Test_push_line:
    def test_情報行の前後で名前と詳細に振り分ける(self):
        reader = MonsterInfoReader()
        reader.push_line("名前行1")
        reader.push_line("名前行2")
        reader.push_line("=== Num:1")
        reader.push_line("詳細行1")
        reader.push_line("詳細行2")

        assert reader.name_lines == ["名前行1", "名前行2"]
        assert reader.info_line == "=== Num:1"
        assert reader.detail_lines == ["詳細行1", "詳細行2"]

    def test_clearで状態が初期化される(self):
        reader = MonsterInfoReader()
        reader.push_line("名前")
        reader.push_line("=== Num:1")
        reader.push_line("詳細")
        reader.clear()

        assert reader.name_lines == []
        assert reader.info_line == ""
        assert reader.detail_lines == []
        assert not reader.has_complete_data()

    def test_名前と情報行と詳細行が揃って初めて完全なデータ(self):
        reader = MonsterInfoReader()
        assert not reader.has_complete_data()
        reader.push_line("名前")
        assert not reader.has_complete_data()
        reader.push_line("=== Num:1")
        assert not reader.has_complete_data()
        reader.push_line("詳細")
        assert reader.has_complete_data()


class Test_parse:
    def test_通常のモンスター(self):
        result = parse_one(SIMPLE_ENTRY)

        assert result["id"] == "16"
        assert result["name"] == "グリッド・バグ"
        assert result["english_name"].strip() == "Grid bug"
        assert result["is_unique"] is False
        assert result["symbol"] == "紫の 'I'"
        assert result["level"] == "1"
        assert result["rarity"] == "1"
        assert result["speed"] == "+0"
        assert result["hp"] == "2d3"
        assert result["ac"] == "12"
        assert result["exp"] == "1"
        assert result["detail"] == "小さな紫色のピカピカ光る虫だ。"

    def test_ユニークは先頭の記号で判定する(self):
        result = parse_one(
            "[U] 農夫マゴット/Farmer Maggot (明るい茶色の 't')\n"
            "=== Num:34  Lev:2  Rar:1  Spd:+0  Hp:220  Ac:10  Exp:5\n"
            "彼は畑からキノコを取り返そうとしている。\n"
        )

        assert result["is_unique"] is True
        assert result["name"] == "農夫マゴット"

    def test_速度は符号付きで取得できる(self):
        result = parse_one(
            "疾風のモンスター/Fast one (白い 'x')\n"
            "=== Num:9  Lev:1  Rar:1  Spd:-10  Hp:1d1  Ac:1  Exp:1\n"
            "遅い。\n"
        )

        assert result["speed"] == "-10"

    def test_名前が複数行に折り返されていても連結する(self):
        # 非常に長い名前のモンスターはスポイラー上で折り返される
        # (コミット 669d4c7 の回帰テスト)
        # 日本語名は改行を削除、英語名は改行を空白に変換して連結される
        result = parse_one(
            "[U] 無敵の恐れ知らずの官能的なる不可思議なる魅惑の頑健なる勤勉なる圧倒的な\n"
            "る華麗なる灰色の王子『強靭なるゾート』/TOUGH ZOTE, the INVINCIBLE\n"
            "FEARLESS GREY PRINCE  (青灰色の 'I')\n"
            "=== Num:1259  Lev:76  Rar:3  Spd:+20  Hp:7000  Ac:170  Exp:36500\n"
            "勇者の幻影。\n"
        )

        assert result["name"] == (
            "無敵の恐れ知らずの官能的なる不可思議なる魅惑の頑健なる勤勉なる圧倒的なる"
            "華麗なる灰色の王子『強靭なるゾート』"
        )
        assert result["english_name"].strip() == (
            "TOUGH ZOTE, the INVINCIBLE FEARLESS GREY PRINCE"
        )
        assert result["symbol"] == "青灰色の 'I'"
        assert result["is_unique"] is True

    def test_日本語名がない名前行では日本語名が空になる(self):
        # 名前行の正規表現は "日本語名/英語名" の "/" を省略可能としている
        result = parse_one(
            "Grid bug (紫の 'I')\n"
            "=== Num:16  Lev:1  Rar:1  Spd:+0  Hp:2d3  Ac:12  Exp:1\n"
            "詳細。\n"
        )

        assert result["name"] == ""
        assert result["english_name"].strip() == "Grid bug"
        assert result["symbol"] == "紫の 'I'"

    def test_データが不完全な場合はNoneを返す(self):
        reader = MonsterInfoReader()
        reader.push_line("名前だけ/Name only (白い 'x')")

        assert reader.parse() is None

    def test_名前行が想定の形式でない場合はNoneを返す(self):
        result = parse_raw(
            "括弧のない名前\n"
            "=== Num:1  Lev:1  Rar:1  Spd:+0  Hp:1d1  Ac:1  Exp:1\n"
            "詳細。\n"
        )

        assert result is None

    def test_情報行が想定の形式でない場合はNoneを返す(self):
        result = parse_raw(
            "グリッド・バグ/Grid bug (紫の 'I')\n" "=== 想定外の形式\n" "詳細。\n"
        )

        assert result is None


class Test_get_mon_info_list:
    def test_空行区切りで複数体を取得できる(self, mon_info_txt):
        results = list(MonsterInfoReader().get_mon_info_list(mon_info_txt))

        assert [r["id"] for r in results] == ["16", "34", "1259", "110"]

    def test_不完全なブロックは読み飛ばされる(self, mon_info_txt):
        results = list(MonsterInfoReader().get_mon_info_list(mon_info_txt))

        # fixture には情報行のないブロックが含まれるが結果には現れない
        assert all("名前しかない" not in r["name"] for r in results)

    def test_詳細行は改行なしで連結される(self, mon_info_txt):
        results = {
            r["id"]: r for r in MonsterInfoReader().get_mon_info_list(mon_info_txt)
        }

        assert results["16"]["detail"] == (
            "小さな紫色のピカピカ光る虫だ。それは通常地下 1 階で出現し、通常の速度で動いている。"
        )

    def test_末尾に空行がないと最後のブロックは取得されない(self):
        # 現状の実装ではループ終了後に parse() を呼ばないため、
        # 最終ブロックの後に空行が必要 (本家のスポイラーは常に空行で終わる)
        results = list(MonsterInfoReader().get_mon_info_list(SIMPLE_ENTRY.rstrip("\n")))

        assert results == []

    def test_日本語名がないモンスターがあっても他の行は取得できる(self):
        # 1体分のパースで例外が出ると更新処理全体が止まってしまうため、
        # 想定外の名前行があっても読み進められること
        text = (
            "Grid bug (紫の 'I')\n"
            "=== Num:16  Lev:1  Rar:1  Spd:+0  Hp:2d3  Ac:12  Exp:1\n"
            "詳細1。\n"
            "\n"
            "大ネズミ/Giant rat (白い 'r')\n"
            "=== Num:110  Lev:5  Rar:1  Spd:+0  Hp:3d5  Ac:8  Exp:2\n"
            "詳細2。\n"
            "\n"
        )

        results = list(MonsterInfoReader().get_mon_info_list(text))

        assert [r["id"] for r in results] == ["16", "110"]
        assert results[0]["name"] == ""
        assert results[1]["name"] == "大ネズミ"

    def test_1体ごとに状態がリセットされる(self, mon_info_txt):
        results = list(MonsterInfoReader().get_mon_info_list(mon_info_txt))

        # 前のモンスターの詳細が次のモンスターに混ざらないこと
        assert results[1]["detail"] == "彼は畑からキノコを取り返そうとしている。"
