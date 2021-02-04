import os
import re
import sqlite3
from dataclasses import dataclass
from typing import List

import discord
from discord.ext import commands
from fuzzywuzzy import fuzz

import CandidatesSelector
from ErrorCatchingArgumentParser import ErrorCatchingArgumentParser


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
    def __init__(self, bot: commands.Bot, config: dict):
        self.mon_info_file = os.path.expanduser(config["mon_info_file"])
        self.mon_info_db_path = os.path.expanduser(config["mon_info_db_path"])
        self.create_monster_info_db()
        self.load_mon_info()
        self.bot = bot

        self.parser = ErrorCatchingArgumentParser(
            prog="$mon", add_help=False,
            description="モンスターを名称の一部で検索し、情報を表示します。"
            "複数のモンスターがヒットした場合は候補を表示し、リアクションにより選択します。"
            "一件もヒットしなかった場合は、あいまい検索により候補を表示します。")
        self.parser.add_argument(
            "-e", "--english", action="store_true", default=False,
            help="英語名で検索する / Search by English name")
        self.parser.add_argument(
            "-h", "--help", action="store_true", default=False,
            help="このヘルプメッセージを表示する")
        self.parser.add_argument("name", help="検索するモンスターの名称の一部", nargs='?')

    @commands.command()
    async def mon(self, ctx: commands.Context, *args):
        try:
            parse_result = self.parser.parse_args(args)
        except Exception as e:
            await self.send_error(ctx, str(e), self.parser.format_help())
            return
        if len(args) == 0 or parse_result.help:
            await self.send_error(ctx, "ヘルプ", self.parser.format_help())
            return

        search_name = parse_result.name.lower()
        name_key = "english_name" if parse_result.english else "name"
        candidates = [m for m in self.mon_info_list if search_name in m[name_key].lower()]
        if not candidates:
            suggests = sorted(
                self.mon_info_list,
                key=lambda m: fuzz.partial_ratio(m[name_key].lower(), search_name), reverse=True
            )[:10]
            await self.choice_and_send_mon_info(ctx, "もしかして:", suggests, name_key)
        elif len(candidates) == 1:
            await self.send_mon_info(ctx, candidates[0])
        elif len(candidates) <= 10:
            await self.choice_and_send_mon_info(ctx, "候補:", candidates, name_key)
        else:
            await self.send_error(ctx, "エラー", "候補が多すぎます")

    async def choice_and_send_mon_info(
            self, ctx: commands.Context, choice_msg: str, mon_candidates: List[dict], name_key: str):
        choice = await CandidatesSelector.select(ctx, choice_msg, [mon[name_key] for mon in mon_candidates])
        if choice is not None:
            await self.send_mon_info(ctx, mon_candidates[choice])

    async def send_error(self, ctx: commands.Context, error_title: str, error_msg: str):
        embed = discord.Embed(title=error_title, description=error_msg, color=discord.Color.red())
        await ctx.reply(embed=embed)

    async def send_mon_info(self, ctx: commands.Context, mon_info):
        title = "[U] " if mon_info["is_unique"] else ""
        title += "{name} / {english_name} ({symbol})".format(**mon_info)
        description = "ID:{id}  階層:{level}  レア度:{rarity}  加速:{speed}  HP:{hp}  AC:{ac}  Exp:{exp}\n\n"\
            .format(**mon_info)
        description += self.get_mon_info_detail(mon_info["id"])
        embed = discord.Embed(title=title, description=description)
        await ctx.reply(embed=embed)

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
