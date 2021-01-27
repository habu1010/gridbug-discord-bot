import asyncio
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import List

import discord
from discord.ext import commands
from fuzzywuzzy import fuzz


@dataclass
class MonInfoReader:
    name_lines: List[str]
    detail_lines: List[str]
    info_line: str = None

    def __init__(self):
        self.clear()

    def clear(self):
        self.name_lines = []
        self.detail_lines = []
        self.info_line = None

    def has_complete_data(self):
        return self.name_lines and self.info_line and self.detail_lines

    def push_line(self, line: str):
        if line.startswith('==='):
            self.info_line = line
        elif self.info_line:
            self.detail_lines.append(line)
        else:
            self.name_lines.append(line)

    def get_mon_info_list(self, mon_info_file: str):
        with open(mon_info_file, encoding='euc_jp') as f:
            lines = (line.strip() for line in f.readlines())

        for line in lines:
            if not line:
                if self.has_complete_data():
                    yield self.parse()
                self.clear()
            else:
                self.push_line(line)

    def parse(self):
        # モンスター名の解析
        name_line = '\n'.join(self.name_lines)
        m = re.match(r"^(\[.\])?\s*(?:(.+)\/)?(.+)\s*\((.+?)\)$", name_line,
                     flags=re.DOTALL)
        name = m[2].replace('\n', '')
        english_name = m[3].replace('\n', ' ')
        is_unique = True if m[1] else False
        symbol = m[4].replace('\n', '')

        # モンスター情報の解析
        m = re.match(r"^=== Num:(\d+)  Lev:(\d+)  Rar:(\d+)  Spd:(.+)  Hp:(.+)  Ac:(\d+)  Exp:(\d+)",
                     self.info_line)
        result = {
            'id': m[1],
            'name': name,
            'english_name': english_name,
            'is_unique': is_unique,
            'symbol': symbol,
            'level': m[2],
            'rarity': m[3],
            'speed': m[4],
            'hp': m[5],
            'ac': m[6],
            'exp': m[7],
            'detail': ''.join(self.detail_lines)
        }
        return result


class MonsterSpoiler(commands.Cog):
    NUM_EMOJIS = [
        '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟'
    ]

    def __init__(self, bot: commands.Bot, config: dict):
        self.mon_info_file = os.path.expanduser(config["mon_info_file"])
        self.mon_info_db_path = os.path.expanduser(config["mon_info_db_path"])
        self.create_monster_info_db()
        self.load_mon_info()
        self.bot = bot

    @commands.command()
    async def mon(self, ctx: commands.Context, name: str):
        candidates = [m for m in self.mon_info_list if name in m["name"]]
        if not candidates:
            suggests = sorted(
                self.mon_info_list,
                key=lambda m: fuzz.ratio(m["name"], name), reverse=True
            )[:10]
            await self.choice_and_send_mon_info(ctx, "もしかして:", suggests)
        elif len(candidates) == 1:
            await self.send_mon_info(ctx, candidates[0])
        elif len(candidates) <= 10:
            await self.choice_and_send_mon_info(ctx, "候補:", candidates)
        else:
            await self.send_error(ctx, "候補が多すぎます")

    async def choice_and_send_mon_info(self, ctx: commands.Context, choice_msg: str, mon_candidates):
        msg = await self.send_mon_candidates(ctx, choice_msg, mon_candidates)
        choice = await self.wait_for_choice(ctx, msg)
        await msg.delete()
        if choice is not None:
            await self.send_mon_info(ctx, mon_candidates[choice])

    async def send_error(self, ctx: commands.Context, error_msg: str):
        embed = discord.Embed(title=error_msg, color=discord.Color.red())
        await ctx.reply(embed=embed)

    async def send_mon_info(self, ctx: commands.Context, mon_info):
        title = "[U] " if mon_info["is_unique"] else ""
        title += "{name} / {english_name} ({symbol})".format(**mon_info)
        description = "ID:{id}  階層:{level}  レア度:{rarity}  加速:{speed}  HP:{hp}  AC:{ac}  Exp:{exp}\n\n"\
            .format(**mon_info)
        description += self.get_mon_info_detail(mon_info["id"])
        embed = discord.Embed(title=title, description=description)
        await ctx.reply(embed=embed)

    async def send_mon_candidates(self, ctx: commands.Context, choice_msg: str, mon_candidates):
        description = '\n'.join([num + " " + mon["name"] for num, mon in zip(self.NUM_EMOJIS, mon_candidates)])
        embed = discord.Embed(title=choice_msg, description=description)
        msg: discord.Message = await ctx.reply(embed=embed)
        for i in range(len(mon_candidates)):
            await msg.add_reaction(self.NUM_EMOJIS[i])
        return msg

    async def wait_for_choice(self, ctx: commands.Context, candidates_msg: discord.Message):
        def check(payload: discord.RawReactionActionEvent):
            return \
                ctx.message.author.id == payload.user_id and \
                payload.message_id == candidates_msg.id and \
                str(payload.emoji) in self.NUM_EMOJIS
        try:
            payload = await self.bot.wait_for('raw_reaction_add', timeout=15.0, check=check)
        except asyncio.TimeoutError:
            return None
        for i, emoji in enumerate(self.NUM_EMOJIS):
            if str(payload.emoji) == emoji:
                return i
        return None

    def get_mon_info_detail(self, monster_id):
        with sqlite3.connect(self.mon_info_db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT detail FROM mon_info WHERE id = :id",
                      {"id": monster_id})
            detail = c.fetchone()
        return detail[0] if detail else ""

    def load_mon_info(self):
        with sqlite3.connect(self.mon_info_db_path) as conn:
            c = conn.cursor()
            c.row_factory = sqlite3.Row
            c.execute(
                '''
SELECT id, name, english_name, is_unique, symbol, level, rarity, speed, hp, ac, exp
    FROM mon_info
'''
            )
            self.mon_info_list = c.fetchall()

    def init_mon_info_db(self):
        with sqlite3.connect(self.mon_info_db_path) as con:
            con.execute('DROP TABLE IF EXISTS mon_info')
            con.execute(
                '''
CREATE TABLE mon_info(
    id INTEGER PRIMARY KEY,
    name TEXT,
    english_name TEXT,
    is_unique INTEGER,
    symbol TEXT,
    level INTEGER,
    rarity INTEGER,
    speed INTEGER,
    hp TEXT,
    ac INTEGER,
    exp INTEGER,
    detail TEXT
)
'''
            )

    def create_monster_info_db(self):
        self.init_mon_info_db()
        mon_info_reader = MonInfoReader()
        with sqlite3.connect(self.mon_info_db_path) as conn:
            c = conn.cursor()
            c.executemany(
                '''
INSERT INTO mon_info VALUES(
    :id, :name, :english_name, :is_unique, :symbol, :level, :rarity, :speed, :hp, :ac, :exp, :detail
)
''',
                mon_info_reader.get_mon_info_list(self.mon_info_file)
            )


def setup(bot):
    bot.add_cog(MonsterSpoiler(bot, bot.ext))
