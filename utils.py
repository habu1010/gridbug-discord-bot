# 共通ユーティリティ関数


def limit_str_length(text: str, max_length: int) -> str:
    """
    文字列がmax_lengthを超える場合、max_length-3文字+"..."で切る。
    max_lengthが3以下の場合は、省略せずにそのままmax_length文字までを返す。
    """
    # max_lengthが3以下の場合は"..."を追加する余地がないため、そのまま切り取る
    if max_length <= 3:
        return text[:max_length]
    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text
