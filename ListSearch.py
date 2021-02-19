from typing import Dict, List, Tuple, Union

from discord.ext import commands
from fuzzywuzzy import fuzz

import CandidatesSelector


async def search(
        ctx: commands.Context, items: List[Dict],
        search_str: str, name_key: str, ename_key: str,
        english: bool = False) -> Tuple[Union[Dict, None], Union[str, None]]:
    """リストから検索を行う

    リストから、search_strで与えた文字列が、itemsで与えたリストの要素である
    辞書の指定したキーの値に一致するものを検索する。
    部分一致で検索し、複数の候補があった場合は候補を表示して選択させる。
    部分一致で一致するものがなかった場合は曖昧検索により候補を表示して選択させる。

    部分一致検索は、まず辞書のキーをname_keyで検索し、一致しなければename_keyにより検索する。
    ただし、englishがTrueの場合はename_keyのみ検索する。

    Args:
        ctx (commands.Context): discord.pyのContext
        items (List[Dict]): 検索を行うリスト
        search_str (str): 検索する文字列
        name_key (str): 検索の時に参照する辞書のキー
        ename_key (str): 英語名検索の時に山椒する辞書のキー
        english (bool, optional): 英語名検索をする. Defaults to False.

    Returns:
        Tuple[Union[Dict, None], Union[str, None]]: 検索結果のタプルを返す。
        第1要素は検索結果があった場合はリスト中のヒットした要素、検索結果がなければNoneを返す。
        第2要素は検索でエラーが発生したらエラーメッセージの文字列、発生しなければNoneを返す。
    """
    candidates = []

    if not english:
        candidates = [i for i in items if search_str in i[name_key]]
    if not candidates:
        search_str = search_str.lower()
        candidates = [i for i in items if search_str in str.lower(i[ename_key])]

    name = ename_key if english else name_key

    if not candidates:
        suggests = sorted(
            items,
            key=lambda x: fuzz.partial_ratio(search_str, str.lower(x[name])), reverse=True
        )[:10]
        choice = await CandidatesSelector.select(ctx, "もしかして:", [i[name] for i in suggests])
        return (suggests[choice] if choice is not None else None, None)
    elif len(candidates) == 1:
        return (candidates[0], None)
    elif len(candidates) <= 10:
        choice = await CandidatesSelector.select(ctx, "候補:", [i[name] for i in candidates])
        return (candidates[choice] if choice is not None else None, None)
    else:
        return (None, f"候補が多すぎます ({len(candidates)} 件)")
