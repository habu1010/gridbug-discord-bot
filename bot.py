import asyncio
import logging
import os
from typing import Any

import discord
import yaml
from discord.ext import commands


class Bot(commands.Bot):
    # 現在ロード中の拡張の設定。load_extension() の直前に代入され、
    # 各モジュールの setup() の中だけで有効な一時的な受け渡し用の属性。
    ext: dict[str, Any]

    def __init__(
        self,
        command_prefix: list[str],
        *,
        intents: discord.Intents,
        bot_config: dict[str, Any],
    ):
        super().__init__(command_prefix, intents=intents)
        self.bot_config = bot_config

    async def setup_hook(self) -> None:
        # extensions: の下を全部コメントアウトすると None になる
        for ext in self.bot_config.get("extensions") or []:
            # 1つの拡張が読み込めなくても (設定に残った削除済みの拡張名、setup() の
            # 失敗、設定の書き間違いなど)、bot 全体が起動しなくならないよう、
            # ログに残して残りを読み込む
            try:
                await self.load_configured_extension(ext)
            except Exception:
                logging.getLogger(__name__).exception(
                    f"拡張 {extension_label(ext)} を読み込めませんでした"
                )

        # 各拡張が登録したスラッシュコマンドを Discord に登録する。
        # 失敗してもプレフィックス付きのコマンドは使えるので、起動は続ける
        try:
            await self.tree.sync()
        except (discord.HTTPException, discord.app_commands.AppCommandError) as e:
            logging.getLogger(__name__).warning(
                f"スラッシュコマンドを登録できませんでした: {e}"
            )

    async def load_configured_extension(self, ext: dict[str, Any]) -> None:
        """設定の extensions の1件 (拡張の名前と設定の辞書) に従って拡張を読み込む"""
        extension_name = ext["name"]
        if logging_level := ext.get("logging_level"):
            logging.getLogger(extension_name).setLevel(logging_level)
        self.ext = ext
        await self.load_extension(extension_name)


def extension_label(ext: object) -> str:
    """ログに出す拡張の名前

    設定には API キーなども含まれうるので、設定の辞書の name 以外は出さない。
    """
    if isinstance(ext, dict) and "name" in ext:
        return str(ext["name"])
    return f"(名前を読めない {type(ext).__name__} の設定)"


async def main() -> None:
    with open(os.path.expanduser("~/.bot-config.yml"), "r") as f:
        bot_config = yaml.full_load(f)

    logging.basicConfig(level=bot_config.get("logging_level", "WARNING"))

    intents = discord.Intents.default()
    intents.message_content = True

    bot = Bot(
        ["$", "!", "?", "＄", "！", "？"],
        intents=intents,
        bot_config=bot_config,
    )
    await bot.start(bot_config["token"])


if __name__ == "__main__":
    asyncio.run(main())
