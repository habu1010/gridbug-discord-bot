from collections.abc import Callable, Coroutine
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands
from fuzzywuzzy import fuzz

from utils import limit_str_length

# 検索対象の要素 (名前などのキーを持つ辞書)
type Item = dict[str, Any]

# 検索完了時に呼ばれるコールバックの型
type OnFound[T] = Callable[[commands.Context, Item, T], Coroutine[Any, Any, None]]

# 検索エラー時に呼ばれるコールバックの型
type OnError = Callable[[commands.Context, str], Coroutine[Any, Any, None]]


class SelectView[T](discord.ui.View):

    def __init__(
        self,
        ctx: commands.Context,
        on_selected: OnFound[T],
        callback_arg: T,
    ):
        super().__init__()
        self.on_selected = on_selected
        self.callback_arg = callback_arg
        self.ctx = ctx


class SelectButton(discord.ui.Button):
    MAX_LABEL_LENGTH = 80

    def __init__(self, item: Item, label: str):
        super().__init__(
            label=limit_str_length(label, self.MAX_LABEL_LENGTH),
            style=discord.ButtonStyle.gray,
        )
        self.item = item

    async def callback(self, interaction: discord.Interaction) -> None:
        if not isinstance(self.view, SelectView):
            return
        if interaction.user.id != self.view.ctx.message.author.id:
            return

        # 候補のメッセージは、インタラクションに応答してから webhook 経由で消す。
        # チャンネル経由で消すと、bot がチャンネルを見られない場合 (スラッシュコマンドは
        # その場合でも使える) に権限が無く失敗するため
        await interaction.response.defer()
        await interaction.delete_original_response()

        view = self.view
        await view.on_selected(view.ctx, self.item, view.callback_arg)


def find_candidates(
    items: list[Item],
    search_str: str,
    name_key: str,
    ename_key: str,
    english: bool = False,
) -> tuple[list[Item], str]:
    """search_str を名前に部分一致で含む要素を探す

    まず name_key で探し、一致しなければ ename_key で大文字小文字を区別せずに探す。
    ただし、english が True の場合は ename_key でのみ探す。

    Returns:
        一致した要素のリストと、一致を判定したキー
    """
    if not english:
        candidates = [i for i in items if search_str in i[name_key]]
        if candidates:
            return candidates, name_key

    search_str = search_str.lower()
    return [i for i in items if search_str in str.lower(i[ename_key])], ename_key


# Discord のオートコンプリートの候補数と、候補の名前・値の文字数の上限
MAX_CHOICES = 25
MAX_CHOICE_LENGTH = 100


def autocomplete_choices(
    items: list[Item],
    current: str,
    name_key: str,
    ename_key: str,
    english: bool = False,
) -> list[app_commands.Choice[str]]:
    """スラッシュコマンドの名前の引数に出すオートコンプリートの候補を作る

    search() と同じく部分一致で探し、前方一致するものを先に並べる。
    候補の値は名前そのもの (上限を超える分は切り捨て) なので、
    選ばれた値で search() を呼べば完全一致か部分一致でその要素が見つかる。
    """
    if not current:
        return []

    candidates, matched_key = find_candidates(
        items, current, name_key, ename_key, english
    )
    # sorted は安定なので、前方一致・部分一致それぞれの中では元の並びを保つ
    current = current.lower()
    candidates = sorted(
        candidates, key=lambda i: not str(i[matched_key]).lower().startswith(current)
    )
    names = [str(i[matched_key]) for i in candidates[:MAX_CHOICES]]
    return [
        app_commands.Choice(
            name=limit_str_length(n, MAX_CHOICE_LENGTH), value=n[:MAX_CHOICE_LENGTH]
        )
        for n in names
    ]


async def search[T](
    ctx: commands.Context,
    on_found: OnFound[T],
    on_error: OnError,
    callback_arg: T,
    items: list[Item],
    search_str: str,
    name_key: str,
    ename_key: str,
    english: bool = False,
) -> None:
    """リストから検索を行う

    リストから、search_strで与えた文字列が、itemsで与えたリストの要素である
    辞書の指定したキーの値に一致するものを検索する。
    部分一致で検索し、複数の候補があった場合は候補を表示して選択させる。
    部分一致で一致するものがなかった場合は曖昧検索により候補を表示して選択させる。

    部分一致の判定の規則は find_candidates() を参照。

    Args:
        ctx (commands.Context): コマンド実行コンテキスト
        on_found: 検索完了時に呼ばれるコールバック
        on_error: 検索エラーが発生した時に呼ばれるコールバック
        items (list[Item]): 検索を行うリスト
        search_str (str): 検索する文字列
        name_key (str): 検索の時に参照する辞書のキー
        ename_key (str): 英語名検索の時に参照する辞書のキー
        english (bool, optional): 英語名検索をする. Defaults to False.
    """
    candidates, matched_key = find_candidates(
        items, search_str, name_key, ename_key, english
    )

    name = ename_key if english else name_key
    query = search_str.lower()

    # 完全一致チェック
    # 実際に部分一致したキーで、英語名検索に合わせて大文字小文字を区別せずに比較する
    exact_matches = [
        i for i in candidates if str.lower(i.get(matched_key, "")) == query
    ]
    if len(exact_matches) == 1:
        await on_found(ctx, exact_matches[0], callback_arg)
        return

    if not candidates:
        suggests = sorted(
            items,
            key=lambda x: fuzz.partial_ratio(query, str.lower(x[name])),
            reverse=True,
        )[:10]
        view = SelectView(ctx, on_found, callback_arg)
        for i in suggests:
            view.add_item(SelectButton(i, i[name]))
        await ctx.reply("もしかして:", view=view, delete_after=15)
    elif len(candidates) == 1:
        await on_found(ctx, candidates[0], callback_arg)
    elif len(candidates) <= 10:
        view = SelectView(ctx, on_found, callback_arg)
        for i in candidates:
            view.add_item(SelectButton(i, i[name]))
        await ctx.reply("候補:", view=view, delete_after=15)
    else:
        await on_error(ctx, f"候補が多すぎます ({len(candidates)} 件)")
