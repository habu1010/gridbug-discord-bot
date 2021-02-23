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
    return await ctx.reply(embed=embed)


async def add_candidates_select_reactions(candidates_msg: discord.Message, candidate_num: int):
    for num in NUM_EMOJIS[:candidate_num]:
        await candidates_msg.add_reaction(num)


async def wait_for_selection(ctx: commands.Context, candidates_msg: discord.Message, candidate_num: int):
    def check(payload: discord.RawReactionActionEvent):
        return \
            ctx.message.author.id == payload.user_id and \
            payload.message_id == candidates_msg.id and \
            str(payload.emoji) in NUM_EMOJIS[:candidate_num]

    add_reaction_task = asyncio.create_task(add_candidates_select_reactions(candidates_msg, candidate_num))

    try:
        payload = await ctx.bot.wait_for('raw_reaction_add', timeout=15.0, check=check)
    except asyncio.TimeoutError:
        return None
    finally:
        add_reaction_task.cancel()

    return NUM_EMOJIS.index(str(payload.emoji))
