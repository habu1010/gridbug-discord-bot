import sqlite3
import os
import re

import discord
from discord.ext import commands


class Note(commands.Cog):
    NOTE_DB = os.path.expanduser("~/notes.db")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if self.bot.user.id not in (i.id for i in message.mentions):
            # 自分がMentionされていない
            return

        # Mention部分を取り除く
        key = re.sub(r'<@!\d+>', '', message.content).strip()

        await message.reply(self.__get_note(key))

    def __get_note(self, key):
        sql = "SELECT * from notes WHERE key = :key"
        with sqlite3.connect(self.NOTE_DB) as con:
            con.row_factory = sqlite3.Row
            c = con.execute(sql, {'key': key})
            rows = c.fetchall()
        if len(rows) > 0:
            notes = [row['value'] for row in rows]
            return '\n'.join(notes)
        else:
            return '{0} とは何ですか？'.format(key)


def setup(bot: commands.Bot):
    bot.add_cog(Note(bot))


def create_db():
    with sqlite3.connect('notes.db') as con:
        sql = '''
CREATE TABLE notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT,
    value TEXT
)
'''
        con.execute(sql)
        con.execute("CREATE INDEX key_index ON notes(key)")


if __name__ == '__main__':
    # create_db()
    import fileinput
    # pattern = re.compile(r"(.+) :#: (.+)")
    # sql = "INSERT INTO notes(key, value) VALUES(:key, :value)"
    # with sqlite3.connect('notes.db') as con:
    #    for line in fileinput.input():
    #        m = pattern.match(line)
    #        if m is not None:
    #            key, value = m.groups()
    #            con.execute(sql, {'key': key, 'value': value})#

    sql = "SELECT * from notes WHERE key = :key"
    with sqlite3.connect('notes.db') as con:
        con.row_factory = sqlite3.Row
        c = con.execute(sql, {'key': 'ばぐ'})
        res = c.fetchall()
    print(res[0]['value'])
    print(res[1]['value'])
    print(res[2]['value'])
