import asyncio
from typing import List

import discord
from discord.ext import commands


NUM_EMOJIS = [
    '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟'
]


async def select(ctx: commands.Context, prompt_msg: str, candidates: List[str]):
    msg = await send_candidates_msg(ctx, prompt_msg, candidates)
    selection = await wait_for_selection(ctx, msg, len(candidates))
    await msg.delete()
    return selection


async def send_candidates_msg(ctx: commands.Context, prompt_msg: str, candidates: List[str]):
    candidates_text = '\n'.join([n + " " + c for n, c in zip(NUM_EMOJIS, candidates)])
    embed = discord.Embed(title=prompt_msg, description=candidates_text)
    msg: discord.Message = await ctx.reply(embed=embed)
    for num in NUM_EMOJIS[:len(candidates)]:
        await msg.add_reaction(num)
    return msg


async def wait_for_selection(ctx: commands.Context, candidates_msg: discord.Message, candidate_num: int):
    def check(payload: discord.RawReactionActionEvent):
        return \
            ctx.message.author.id == payload.user_id and \
            payload.message_id == candidates_msg.id and \
            str(payload.emoji) in NUM_EMOJIS[:candidate_num]
    try:
        payload = await ctx.bot.wait_for('raw_reaction_add', timeout=15.0, check=check)
    except asyncio.TimeoutError:
        return None

    return NUM_EMOJIS.index(str(payload.emoji))
