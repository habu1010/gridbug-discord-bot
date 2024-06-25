import json
import re
from typing import Any


def parse_jsonc(jsonc_data: str) -> Any:
    """jsonc形式の文字列をパースする

    jsonc形式の文字列を受け取り、コメントを削除してjsonとしてパースする

    Args:
        jsonc_data (str): jsonc形式の文字列

    Returns:
        Any: パースした結果のオブジェクト
    """
    json_data = re.sub(r"/\*[\s\S]*?\*/|//.*", "", jsonc_data)
    json_obj = json.loads(json_data)
    return json_obj
