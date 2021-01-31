gridbug-discord-bot
====

Discordの[変愚蛮怒](https://hengband.osdn.jp/)公式ギルドのチャンネル[#ぐりっどばぐ](https://discord.gg/8xW6q5SqXY)で稼働しているbot

Description
----

gridbbug-discord-botには、以下の機能があります。

- モンスタースポイラー機能 - 変愚蛮怒に出現するモンスターの情報を検索し表示します。
- アーティファクトスポイラー機能 - 変愚蛮怒に出現する固定アーティファクトの情報を検索し表示します。
- RSSフィード通知機能 - RSSフィードをチェックして通知する機能。変愚蛮怒に関連する以下の情報の更新を定期的にチェックし通知しています。
  - [スコアサーバ](https://hengband.osdn.jp/score.html)の新着スコア
  - [変愚蛮怒スポイラー・攻略Wiki](http://mars.kmc.gr.jp/~dis/heng_wiki/index.php)の記事更新
  - [変愚蛮怒プロジェクトページ](https://osdn.net/projects/hengband/)の[フォーラム](https://osdn.net/projects/hengband/forums/)への新規投稿・[チケット](https://osdn.net/projects/hengband/ticket/)の新規投稿・更新(開発用チャンネルへ通知)
- ダイスロール機能 - サイコロを振ります。

Requirements
----

- [discord.py](https://pypi.org/project/discord.py/)
- [feedparser](https://pypi.org/project/feedparser/)
- [bitlyshortener](https://pypi.org/project/bitlyshortener/)
- [fuzzywuzzy](https://pypi.org/project/fuzzywuzzy/)

Usage
----

コマンドは接頭詞に'$'をつけて、「$コマンド名 引数」の形で実行します。
botが居るチャンネル宛か、botに直接DMで送信コマンドを送信することでメッセージに対する返信の形で結果を表示します。

### モンスタースポイラー機能

```
$mon モンスター名
```

部分一致検索を行います。複数の候補(10個以下)がある場合は候補が表示され、リアクションにより選択できます。
候補がヒットしなかった場合は、あいまい検索により近い名前のモンスターを候補として表示します。

<img src="../images/command_example/mon_lousy.png" width="400px">

### アーティファクトスポイラー機能

```
$art 固定アーティファクト名
```

モンスタースポイラー機能と同様です。

<img src="../images/command_example/art_Ringil.png" width="400px">

### ダイスロール機能

```
$roll <N>d<M>
```

ダイス面数がMのサイコロをN回振った結果を表示します。Nは100以下の制限があります。

<img src="../images/command_example/roll_4d5.png" width="400px">

License
----
This software is released under the MIT License, see LICENSE.
