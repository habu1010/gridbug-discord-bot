"""ArtifactSpoiler のテスト

表示文字列を組み立てる describe_* 系と、
DBからアーティファクト情報を組み立てる非同期メソッドを検証する。

ArtifactSpoilerCog は __init__ で checker_task を起動するためテストでは生成しない。
"""

import pytest
from conftest import FakeClientSession, FakeResponse, as_session, read_fixture

from ArtifactSpoiler import ArtifactSpoiler

BASE_URL = "https://example.invalid/hengband/master"


@pytest.fixture
def spoiler(art_db) -> ArtifactSpoiler:
    return ArtifactSpoiler(BASE_URL, art_db)


def a_info(**kwargs) -> dict:
    """a_info の1行を模した辞書を作る (実体は添字アクセスのみなのでdictで代用できる)"""
    row = {
        "is_melee_weapon": 0,
        "is_protective_equipment": 0,
        "is_armor": 0,
        "base_ac": 0,
        "base_dam": "",
        "to_hit": 0,
        "to_dam": 0,
        "to_ac": 0,
        "activate_flag": "NONE",
        "timeout": 0,
        "dice": 0,
        "desc": "なし",
    }
    row.update(kwargs)
    return row


def flag_row(group: str, description: str) -> dict:
    return {"flag_group": group, "description": description}


class Test_describe_to_hit_dam:
    def test_修正が無い装備は表示しない(self, spoiler):
        assert spoiler.describe_to_hit_dam(a_info()) == ""

    def test_近接武器は修正が0でも表示する(self, spoiler):
        assert spoiler.describe_to_hit_dam(a_info(is_melee_weapon=1)) == " (+0,+0)"

    def test_命中とダメージの修正を表示する(self, spoiler):
        row = a_info(is_melee_weapon=1, to_hit=5, to_dam=-3)

        assert spoiler.describe_to_hit_dam(row) == " (+5,-3)"

    def test_鎧でダメージ修正が無い場合は命中修正のみ(self, spoiler):
        row = a_info(is_armor=1, is_protective_equipment=1, to_hit=-4, to_dam=0)

        assert spoiler.describe_to_hit_dam(row) == " (-4)"

    def test_鎧でもダメージ修正があれば両方表示する(self, spoiler):
        row = a_info(is_armor=1, is_protective_equipment=1, to_hit=2, to_dam=3)

        assert spoiler.describe_to_hit_dam(row) == " (+2,+3)"

    def test_武器以外でも修正があれば表示する(self, spoiler):
        assert spoiler.describe_to_hit_dam(a_info(to_hit=1)) == " (+1,+0)"


class Test_describe_ac:
    def test_防具はベースACと修正を表示する(self, spoiler):
        row = a_info(is_protective_equipment=1, base_ac=40, to_ac=20)

        assert spoiler.describe_ac(row) == " [40,+20]"

    def test_防具でなくてもベースACがあれば表示する(self, spoiler):
        assert spoiler.describe_ac(a_info(base_ac=10, to_ac=5)) == " [10,+5]"

    def test_AC修正だけの場合は修正のみ表示する(self, spoiler):
        assert spoiler.describe_ac(a_info(to_ac=15)) == " [+15]"

    def test_ACに関係しない装備は表示しない(self, spoiler):
        assert spoiler.describe_ac(a_info()) == ""

    def test_ベースAC0の防具も表示する(self, spoiler):
        row = a_info(is_protective_equipment=1, base_ac=0, to_ac=0)

        assert spoiler.describe_ac(row) == " [0,+0]"


class Test_describe_flag_group:
    def test_該当グループがなければ空文字(self, spoiler):
        flags = [flag_row("BONUS", "腕力")]

        assert spoiler.describe_flag_group(flags, "耐性: ", "RESISTANCE") == ""

    def test_同じグループのフラグをカンマ区切りで連結する(self, spoiler):
        flags = [
            flag_row("RESISTANCE", "酸"),
            flag_row("BONUS", "腕力"),
            flag_row("RESISTANCE", "火炎"),
        ]

        assert (
            spoiler.describe_flag_group(flags, "耐性: ", "RESISTANCE")
            == "耐性: 酸, 火炎\n "
        )

    def test_見出しが空でも連結できる(self, spoiler):
        flags = [flag_row("MISC", "浮遊")]

        assert spoiler.describe_flag_group(flags, "", "MISC") == "浮遊\n "


class Test_describe_activation:
    def test_発動がなければ空文字(self, spoiler):
        assert spoiler.describe_activation(a_info(activate_flag="NONE")) == ""

    def test_タイムアウト0はいつでも(self, spoiler):
        row = a_info(activate_flag="BERSERK", timeout=0, dice=0, desc="士気高揚")

        assert spoiler.describe_activation(row) == "\n発動: 士気高揚 : いつでも\n"

    def test_ダイスなしはターン毎(self, spoiler):
        row = a_info(activate_flag="SUNLIGHT", timeout=10, dice=0, desc="太陽光線")

        assert spoiler.describe_activation(row) == "\n発動: 太陽光線 : 10 ターン毎\n"

    def test_ダイスありはダイス付きで表示する(self, spoiler):
        row = a_info(
            activate_flag="LIGHT", timeout=10, dice=10, desc="イルミネーション"
        )

        assert (
            spoiler.describe_activation(row)
            == "\n発動: イルミネーション : 10+d10 ターン毎\n"
        )

    def test_TERRORは特殊なタイムアウト表記になる(self, spoiler):
        row = a_info(activate_flag="TERROR", timeout=-1, dice=0, desc="恐慌")

        assert (
            spoiler.describe_activation(row)
            == "\n発動: 恐慌 : 3*(レベル+10) ターン毎\n"
        )

    def test_MURAMASAは特殊なタイムアウト表記になる(self, spoiler):
        row = a_info(activate_flag="MURAMASA", timeout=-1, dice=0, desc="腕力上昇")

        assert (
            spoiler.describe_activation(row) == "\n発動: 腕力上昇 : 確率50%で壊れる\n"
        )

    def test_未知の特殊タイムアウトは不明(self, spoiler):
        row = a_info(activate_flag="NEW_SPECIAL", timeout=-1, dice=0, desc="何か")

        assert spoiler.describe_activation(row) == "\n発動: 何か : 不明\n"


class Test_describe_activation_timeout:
    @pytest.mark.parametrize(
        ("timeout", "dice", "expected"),
        [
            (0, 0, "いつでも"),
            (100, 0, "100 ターン毎"),
            (100, 20, "100+d20 ターン毎"),
            (-1, 0, None),
        ],
    )
    def test_タイムアウト表記(self, spoiler, timeout, dice, expected):
        assert spoiler.describe_activation_timeout(timeout, dice) == expected

    def test_特殊なタイムアウトの表記(self, spoiler):
        assert (
            spoiler.describe_activation_timeout_special("TERROR")
            == "3*(レベル+10) ターン毎"
        )
        assert (
            spoiler.describe_activation_timeout_special("MURAMASA") == "確率50%で壊れる"
        )
        assert spoiler.describe_activation_timeout_special("UNKNOWN") == "不明"


class Test_load_artifacts:
    async def test_全アーティファクトを読み込む(self, spoiler):
        arts = {a["id"]: a for a in await spoiler.load_artifacts()}

        assert set(arts) == {1, 19, 96, 124, 200}

    async def test_通常はアーティファクト名の後にベースアイテム名が付く(self, spoiler):
        arts = {a["id"]: a for a in await spoiler.load_artifacts()}

        assert arts[1]["fullname"] == "ガラドリエルの燦光"

    async def test_二重鉤括弧で始まる名前はベースアイテム名が前に付く(self, spoiler):
        arts = {a["id"]: a for a in await spoiler.load_artifacts()}

        assert arts[19]["fullname"] == "ミスリル・チェイン・メイル『魂の守り手』"

    async def test_FULL_NAMEフラグがあればアーティファクト名のみ(self, spoiler):
        arts = {a["id"]: a for a in await spoiler.load_artifacts()}

        assert arts[96]["fullname"] == "グロンド"

    async def test_英語名は記号が置換される(self, spoiler):
        arts = {a["id"]: a for a in await spoiler.load_artifacts()}

        # "&" は "The" に、"~" は削除される
        assert arts[1]["fullname_en"] == "The Phial of Galadriel"
        assert arts[19]["fullname_en"] == "The Mithril Chain Mail 'Soulkeeper'"

    async def test_FULL_NAMEの英語名もベースアイテム名を含まない(self, spoiler):
        arts = {a["id"]: a for a in await spoiler.load_artifacts()}

        assert arts[96]["fullname_en"] == "The Grond"


class Test_describe_artifact:
    async def get_art(self, spoiler, art_id: int) -> dict:
        arts = {a["id"]: a for a in await spoiler.load_artifacts()}
        return arts[art_id]

    async def test_近接武器はダイスと修正を表示する(self, spoiler):
        art = await self.get_art(spoiler, 96)

        main, detail = await spoiler.describe_artifact(art)

        assert main == "[96] ★グロンド (3d9) (+5,+25) / The Grond"
        assert "対: 邪悪, *善良*" in detail
        assert "武器属性: 焼棄" in detail
        assert "発動: 恐慌 : 3*(レベル+10) ターン毎" in detail
        assert "階層: 100, 希少度: 100, 25.0 kg, $500000" in detail

    async def test_射撃武器は倍率を表示する(self, spoiler):
        art = await self.get_art(spoiler, 124)

        main, detail = await spoiler.describe_artifact(art)

        # XTRA_MIGHT 付きロング・ボウなので x4
        assert (
            main
            == "[124] ★ロング・ボウ『ベルスロンディング』 (x4) (+20,+22) / The Long Bow 'Belthronding'"
        )
        assert detail.startswith("+20の修正: 器用, 隠密")

    async def test_鎧はACを表示する(self, spoiler):
        art = await self.get_art(spoiler, 19)

        main, detail = await spoiler.describe_artifact(art)

        assert main.startswith(
            "[19] ★ミスリル・チェイン・メイル『魂の守り手』 (-4) [40,+20]"
        )
        assert "+2の修正: 耐久" in detail
        assert "耐性: 酸, 火炎" in detail
        assert "経験値維持" in detail
        assert "発動: *体力回復* : 888 ターン毎" in detail

    async def test_発動がないアーティファクト(self, spoiler):
        art = await self.get_art(spoiler, 200)

        main, detail = await spoiler.describe_artifact(art)

        assert main == "[200] ★テストのアミュレット / The Amulet of Test"
        assert "発動" not in detail
        assert "階層: 5, 希少度: 2, 0.1 kg, $100" in detail

    async def test_重さはkg表記に変換される(self, spoiler):
        art = await self.get_art(spoiler, 1)

        _, detail = await spoiler.describe_artifact(art)

        # weight 10 -> 10/20 = 0.5 kg
        assert "0.5 kg" in detail

    async def test_表示順はflag_infoのグループ順に従う(self, spoiler):
        art = await self.get_art(spoiler, 19)

        _, detail = await spoiler.describe_artifact(art)

        assert (
            detail.index("+2の修正")
            < detail.index("耐性:")
            < detail.index("経験値維持")
        )

    async def test_詳細が見つからない場合はメッセージを返す(self, spoiler):
        main, detail = await spoiler.describe_artifact(
            {"id": 99999, "fullname": "無い物", "fullname_en": "Nothing"}
        )

        assert main == "[99999] ★無い物"
        assert detail == "詳細情報が見つかりませんでした"


class Test_download_file:
    async def test_取得したテキストを返す(self, spoiler):
        session = FakeClientSession(
            {"ArtifactDefinitions.jsonc": FakeResponse(200, "body", {"etag": "tag-1"})}
        )

        path = "lib/edit/ArtifactDefinitions.jsonc"

        text = await spoiler.download_file(session, path)

        assert text == "body"
        assert session.requests[0]["url"] == f"{BASE_URL}/{path}"

    async def test_etagを保持して次回のリクエストに使う(self, spoiler):
        path = "lib/edit/ArtifactDefinitions.jsonc"
        session = FakeClientSession(
            {path: [FakeResponse(200, "body", {"etag": "tag-1"}), FakeResponse(304)]}
        )

        await spoiler.download_file(session, path)
        await spoiler.download_file(session, path)

        assert session.requests[0]["headers"] == {"if-none-match": ""}
        assert session.requests[1]["headers"] == {"if-none-match": "tag-1"}

    async def test_200以外はNoneを返す(self, spoiler):
        session = FakeClientSession(FakeResponse(304))

        assert await spoiler.download_file(session, "lib/edit/なにか") is None


class Test_check_for_updates:
    async def test_取得したファイルでDBを更新する(self, tmp_path):
        db_path = str(tmp_path / "art.db")
        spoiler = ArtifactSpoiler(BASE_URL, db_path)
        session = FakeClientSession(
            {
                "ArtifactDefinitions.jsonc": FakeResponse(
                    200, read_fixture("ArtifactDefinitions.jsonc")
                ),
                "BaseitemDefinitions.jsonc": FakeResponse(
                    200, read_fixture("BaseitemDefinitions.jsonc")
                ),
                "activation-info-table.cpp": FakeResponse(
                    200, read_fixture("activation-info-table.cpp")
                ),
            }
        )

        await spoiler.check_for_updates(as_session(session))

        assert len(spoiler.artifacts) == 5
        assert [r["url"].rsplit("/", 1)[-1] for r in session.requests] == [
            "ArtifactDefinitions.jsonc",
            "BaseitemDefinitions.jsonc",
            "activation-info-table.cpp",
        ]

    async def test_更新がなければ既存のリストを保持する(self, spoiler):
        # 事前にDBは作成済みなので、304応答でもアーティファクトは読み込まれる
        session = FakeClientSession(FakeResponse(304))

        await spoiler.check_for_updates(as_session(session))
        loaded = spoiler.artifacts
        assert len(loaded) == 5

        # 2度目は更新もロードも行わず、同じリストを保持したままになる
        await spoiler.check_for_updates(as_session(session))
        assert spoiler.artifacts is loaded
