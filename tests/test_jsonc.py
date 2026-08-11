"""Jsonc.parse_jsonc のテスト"""

import pytest

from Jsonc import parse_jsonc


def test_通常のjsonをパースできる():
    assert parse_jsonc('{"a": 1, "b": [1, 2]}') == {"a": 1, "b": [1, 2]}


def test_行コメントを無視する():
    jsonc = """
{
    // 行コメント
    "a": 1  // 値の後ろの行コメント
}
"""
    assert parse_jsonc(jsonc) == {"a": 1}


def test_ブロックコメントを無視する():
    assert parse_jsonc('{/* ブロック\nコメント */ "a": 1}') == {"a": 1}


@pytest.mark.parametrize(
    ("jsonc", "expected"),
    [
        ('{"a": 1,}', {"a": 1}),
        ('{"a": [1, 2,],}', {"a": [1, 2]}),
        ("[1, 2, 3,]", [1, 2, 3]),
    ],
)
def test_末尾カンマを許容する(jsonc, expected):
    # 本家の定義ファイルには末尾カンマが含まれる (コミット e8c265e の回帰テスト)
    assert parse_jsonc(jsonc) == expected


def test_コメントと末尾カンマの組み合わせ():
    jsonc = """
{
    "artifacts": [
        // 1件目
        { "id": 1, },
    ],  /* 末尾 */
}
"""
    assert parse_jsonc(jsonc) == {"artifacts": [{"id": 1}]}


def test_不正なjsonでは例外を送出する():
    with pytest.raises(Exception):
        parse_jsonc("{this is not json")
