# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

ローグライクゲーム「変愚蛮怒(hengband)」のDiscordギルド向けbot。discord.py製で、変愚蛮怒公式リポジトリの定義ファイル/スポイラーを定期的に取得してSQLiteにキャッシュし、モンスターやアーティファクトの情報検索コマンドを提供する。他にRSS通知、ソース表示、翻訳、ダイスロール機能がある。

## 開発コマンド

```bash
# 仮想環境 (.venv, Python 3.12) の有効化 (fish)
source .venv/bin/activate.fish

# 依存パッケージ
pip install -r requirements.txt

# bot起動 (~/.bot-config.yml が必要)
python bot.py

# テスト (開発用パッケージが必要)
pip install -r requirements-dev.txt
pytest

# 型チェック (設定は pyrightconfig.json)
pyright
```

コミットメッセージは日本語の Conventional Commits 形式 (`feat:` / `fix:` / `chore:` / `style:`)。

### 整形

整形は Black + isort、行長は flake8 の E501 準拠 (`# noqa: E501` の使用実績あり)。

**Blackのバージョンは requirements-dev.txt にピン留めしていない。VSCodeのBlack Formatter拡張 (`ms-python.black-formatter`) が同梱している版に従う** (2026年8月時点で black 26.1.0)。ピン留めすると拡張の自動更新でズレが再発するため。CLIで整形する場合も同じ版を使うこと。同梱版は次で確認できる。

```bash
ls -d ~/.vscode-server/extensions/ms-python.black-formatter-*/bundled/libs/black-*.dist-info
```

black 26.x は日本語を含む行を「東アジア文字は幅2」で数えて折り返し、引数が複数行文字列だけの呼び出し (SQLリテラルなど) では文字列を括弧に寄せる。古い版で整形すると全て元に戻ってしまう。

isort は [.isort.cfg](.isort.cfg) で black プロファイルを指定している。既定のままだと、1行に収まらない import の折り返し方が Black と食い違う (isort の既定は名前を詰めて折り返す形式、Black は1行1名の形式) ため。CLI でも VSCode の isort 拡張でもこの設定が読まれる。

### 型注釈

Python 3.12+ を前提とし、`typing.List` / `Dict` / `Optional` / `Union` は使わず `list` / `dict` / `X | None` / `X | Y` と書く。`Callable` / `Coroutine` / `Iterator` などは `collections.abc` から取る。ジェネリクスは PEP 695 の型パラメータ構文 (`class SelectView[T]` / `def search[T](...)`) を使う。

代入から推論できるローカル変数には付けない。空コンテナの初期化など推論が `list[Unknown]` になる箇所だけ明示する。

pyright (standard モード) のエラーは0件を維持する。テストのスタブ (`FakeClientSession` など) を本番の引数に渡す箇所は、本番側のシグネチャを緩めず [tests/conftest.py](tests/conftest.py) の `as_session()` / `as_interaction()` でキャストする。`FakeContext` は注釈のないfixture引数として渡るためキャスト不要。

`setup()` の引数は、`bot.ext` を読む場合のみ `TYPE_CHECKING` 下で `bot.Bot` を参照して `bot: "Bot"`、読まない場合は `bot: commands.Bot` と書く。

## テスト

[tests/](tests/) 以下に pytest のテストがある。Discord への接続もネットワークI/Oも行わず、DBは全て `tmp_path` 配下に作る。

- HTTP は [tests/conftest.py](tests/conftest.py) の `FakeClientSession` / `FakeResponse` に、`commands.Context` は `FakeContext` に差し替える。
- `MonsterSpoiler` / `ArtifactSpoilerCog` / `RssCheckCog` / `ChannelLogger` は `__init__` で `checker_task.start()` を呼ぶため、テストでインスタンス化しない (必要なら `__new__` で生成して属性を差し込む)。
- コマンド関数は `commands.Command` でラップされているため `Cog.コマンド名.callback(cog, ctx, ...)` の形で直接呼ぶ。
- `discord.ui.View` の生成には実行中のイベントループが必要なので、[ListSearch.py](ListSearch.py) 関連のテストは非同期テストにする (`asyncio_mode = auto`)。
- 本家の定義ファイルの縮小版は [tests/fixtures/](tests/fixtures/) にある。`flag_info.txt` だけはリポジトリの実ファイルを読んで回帰テストしている。

## 設定ファイル

`~/.bot-config.yml` (リポジトリ外、実行環境ごとに用意) が全ての設定を持つ。

```yaml
token: <Discord Bot Token>
logging_level: WARNING
extensions:
  - name: MonsterSpoiler        # 拡張(Cog)のモジュール名
    logging_level: INFO         # 任意: このモジュールのログレベル
    mon_info_url: ...           # 以降は各Cog固有の設定キー
```

## アーキテクチャ

### 拡張のロードと設定の受け渡し

[bot.py](bot.py) は `extensions` の各エントリについて **`self.ext = ext` を代入した直後に `load_extension()` を呼ぶ**。各モジュールの `setup(bot)` は `bot.ext` を読んで自分の設定辞書を取得する ([MonsterSpoiler.py:92-93](MonsterSpoiler.py#L92-L93) など)。つまり `bot.ext` は「今ロード中の拡張の設定」を指す一時的な受け渡し用の属性であり、`setup()` の中でしか有効でない。新しいCogを追加する際もこの流儀に従うこと。

### 情報取得のパイプライン

モンスター/アーティファクト情報は、いずれも次の流れで扱われる。

1. `@tasks.loop(seconds=300)` の `checker_task` が変愚蛮怒のソース/スポイラーをHTTP取得する。ETag (`if-none-match`) を保持して差分がなければ何もしない。
2. `*InfoReader` クラスが取得したテキストをパースし、SQLiteのテーブルを **DROP して作り直す** (差分更新はしない)。
3. 検索用の軽量なリスト (名前とヘッダ情報のみ) をメモリに読み込んで保持し、詳細は表示時にDBから引く。

- モンスター: [MonsterInfo.py](MonsterInfo.py) が MD5ハッシュ比較 + ETag の二段構えで更新判定し、`mon-info.db` を更新。パースは [MonsterInfoReader.py](MonsterInfoReader.py) (空行区切り・`===` 行始まりのプレーンテキストスポイラー形式)。
- アーティファクト: [ArtifactSpoiler.py](ArtifactSpoiler.py) が `master` / `develop` の2ブランチ分の `ArtifactSpoiler` インスタンス (`art-info-master.db` / `art-info-develop.db`) を持ち、`$art -d` で develop を検索する。取得元は本家の `ArtifactDefinitions.jsonc` / `BaseitemDefinitions.jsonc` / `activation-info-table.cpp` / `spoiler-table.cpp` の4ファイル。

SQLite書き込み系のReader (`ArtifactInfoReader` / `KindInfoReader` / `ActivationInfoReader` / `FlagInfoReader`) は同期 `sqlite3` を使うため、イベントループを塞がないよう `loop.run_in_executor()` 経由で呼ぶ ([ArtifactSpoiler.py:245-248](ArtifactSpoiler.py#L245-L248))。読み出し側は `aiosqlite` を使う。

### アーティファクトのフラグ表示

フラグ名 → 日本語表示名と表示グループ (BONUS/RESISTANCE/MISC など) の対応は、`FlagInfoReader.create_flag_info_table()` が次の順で `flag_info` テーブルに取り込む。

1. 本家の `src/wizard/spoiler-table.cpp` (本家スポイラー出力用の `{ TR_XXX, _("日本語", "English") }` テーブル)。他の定義ファイルと同じく `checker_task` で定期取得する。グループはテーブル名から決める (`SPOILER_TABLE_GROUPS`。未知のテーブル名は MISC)。名前もグループも本家が優先される。
2. [flag_info.txt](flag_info.txt)。本家テーブルに無いフラグ (呪い・光源・XTRA・非表示の IGNORE など) だけを書く。グループ内では本家テーブルのフラグの後ろに、記述順で並ぶ。

どちらにも無いフラグは、フラグ名そのままで MISC の末尾に表示される。その場合 `ArtifactInfoReader.warn_unknown_flags()` が `Unknown flag(s):` を warning ログに出す (ChannelLogger経由でDiscordにも流れる) ので、必要なら flag_info.txt に表示名を追加する。このチェックは `check_for_updates()` が flag_info か a_info を更新した時に呼ぶ。flag_info の `source` 列 (`spoiler-table.cpp` / `flag_info.txt`) が各定義の取得元を示し、本家由来の行が1件も無い間 (DB を作り直した初回起動で spoiler-table.cpp の取得に失敗した時など) は、本家テーブルにあるフラグまで未知と判定してしまうので判定を保留する。

`ArtifactSpoiler.__init__` は flag_info テーブルが無い時 (または `source` 列の無い古いスキーマの時) だけ flag_info.txt から作り、既にあれば前回取り込んだ本家の定義ごと残す (起動直後に spoiler-table.cpp の取得に失敗しても表示名が崩れないように)。spoiler-table.cpp を取得できてもフラグを1件も読めなかった場合も、既存のテーブルを残して warning を出す。

### コマンドの共通パターン

- 接頭辞は `$ ! ? ＄ ！ ？` のいずれも受け付ける。
- 引数解析は `ErrorCatchingArgumentParser` (argparseの `exit()` を例外に変える薄いラッパ)。パース失敗時は `ctx.send_help(ctx.command)` を呼ぶ。ヘルプ本文は **コマンド関数のdocstringがそのままDiscordに表示される** ため、docstringにpositional/optional argumentsを手書きしている。
- 名前検索は [ListSearch.py](ListSearch.py) の `search()` に集約。部分一致 → 完全一致が1件ならそれを採用 → 候補10件以下ならボタン(`SelectView`/`SelectButton`)で選択 → 0件なら fuzzywuzzy であいまい候補を提示、という流れ。ボタンは発言者本人しか押せない。

### Discord APIの制限

Embed title は256文字、ボタンラベルは80文字が上限。長い文字列は [utils.py](utils.py) の `limit_str_length()` で切り詰める。

## デプロイ

main へのpushで [.github/workflows/deploy.yml](.github/workflows/deploy.yml) がrsyncし、リモートで `docker compose up --build -d` を実行する。Dockerfile / compose.yml はこのリポジトリではなくデプロイ先の親ディレクトリにある。

## ローカルの生成物

`mon-info.db` / `art-info-master.db` / `art-info-develop.db` はbot実行時に自動生成されるキャッシュでgit管理外。スキーマを変えた場合は削除して再取得させればよい。
