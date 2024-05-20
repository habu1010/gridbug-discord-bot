from typing import Any, Callable, Coroutine, List, TypeVar

import discord
from discord.ext import commands
from fuzzywuzzy import fuzz

T = TypeVar("T")


class SelectView(discord.ui.View):

    def __init__(
        self,
        ctx: commands.Context,
        on_selected: Callable[[commands.Context, dict, T], Coroutine[Any, Any, None]],
        callback_arg: T,
    ):
        super().__init__()
        self.on_selected = on_selected
        self.callback_arg = callback_arg
        self.ctx = ctx


class SelectButton(discord.ui.Button):
    def __init__(self, item, label: str):
        super().__init__(label=label, style=discord.ButtonStyle.gray)
        self.item = item

    async def callback(self, interaction: discord.Interaction):
        if (interaction.message is None) or not isinstance(self.view, SelectView):
            return
        if interaction.user.id != self.view.ctx.message.author.id:
            return

        await interaction.message.delete()

        view = self.view
        await view.on_selected(view.ctx, self.item, view.callback_arg)


async def search(
    ctx: commands.Context,
    on_found: Callable[[commands.Context, dict, T], Coroutine[Any, Any, None]],
    on_error: Callable[[commands.Context, str], Coroutine[Any, Any, None]],
    callback_arg: T,
    items: List[dict],
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

    部分一致検索は、まず辞書のキーをname_keyで検索し、一致しなければename_keyにより検索する。
    ただし、englishがTrueの場合はename_keyのみ検索する。

    Args:
        ctx (commands.Context): コマンド実行コンテキスト
        on_found: 検索完了時に呼ばれるコールバック
        on_error: 検索エラーが発生した時に呼ばれるコールバック
        items (List[dict]): 検索を行うリスト
        search_str (str): 検索する文字列
        name_key (str): 検索の時に参照する辞書のキー
        ename_key (str): 英語名検索の時に参照する辞書のキー
        english (bool, optional): 英語名検索をする. Defaults to False.
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
            key=lambda x: fuzz.partial_ratio(search_str, str.lower(x[name])),
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
