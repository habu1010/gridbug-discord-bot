"""utils.limit_str_length のテスト"""

import pytest

from utils import limit_str_length


@pytest.mark.parametrize(
    ("text", "max_length", "expected"),
    [
        ("abc", 10, "abc"),  # 上限未満はそのまま
        ("abcde", 5, "abcde"),  # ちょうど上限はそのまま
        ("abcdef", 5, "ab..."),  # 超過分は max_length-3 文字 + "..."
        ("", 10, ""),  # 空文字
        ("あいうえお", 4, "あ..."),  # マルチバイトでも文字数で数える
    ],
)
def test_limit_str_length(text, max_length, expected):
    assert limit_str_length(text, max_length) == expected


@pytest.mark.parametrize("max_length", [0, 1, 2, 3])
def test_limit_str_length_短い上限では省略記号を付けない(max_length):
    # "..." を足す余地がないため、単純に切り詰めるだけになる
    assert limit_str_length("abcdef", max_length) == "abcdef"[:max_length]


def test_limit_str_length_結果は必ず上限以下():
    for max_length in range(0, 20):
        assert len(limit_str_length("0123456789" * 2, max_length)) <= max_length
