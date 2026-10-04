#include "wizard/spoiler-table.h"

/* The artifacts categorized by type */
const std::vector<grouper> group_artifact_list = {
    { { ItemKindType::SWORD }, _("刀剣", "Edged Weapons") },
    { { ItemKindType::LITE }, _("光源", "Light Sources") },
};

const std::vector<flag_desc> stat_flags_desc = { { TR_STR, _("腕力", "STR") }, { TR_INT, _("知能", "INT") }, { TR_WIS, _("賢さ", "WIS") },
    { TR_DEX, _("器用さ", "DEX") },
    { TR_CON, _("耐久力", "CON") }, { TR_CHR, _("魅力", "CHR") } };

const std::vector<flag_desc> pval_flags1_desc = { { TR_MAGIC_MASTERY, _("魔法道具使用能力", "Magic Mastery") }, { TR_STEALTH, _("隠密", "Stealth") },
    { TR_SPEED, _("スピード", "Speed") } };

const std::vector<flag_desc> slay_flags_desc = {
    { TR_SLAY_EVIL, _("邪悪", "Evil") },
    { TR_KILL_EVIL, _("*邪悪*", "XEvil") },
    { TR_SLAY_GOOD, _("善良", "Good") },
    { TR_KILL_GOOD, _("*善良*", "XGood") },
    { TR_SLAY_DEMON, _("悪魔", "Demon") },
    { TR_KILL_DEMON, _("*悪魔*", "XDemon") },
};

/* Elemental brands for weapons */
const std::vector<flag_desc> brand_flags_desc = {
    { TR_BRAND_FIRE, _("焼棄", "Flame Tongue") },
    { TR_BRAND_COLD, _("凍結", "Frost Brand") },
};

const std::vector<flag_desc> resist_flags_desc = {
    { TR_RES_ACID, _("酸", "Acid") },
    { TR_RES_FIRE, _("火炎", "Fire") },
    { TR_RES_COLD, _("冷気", "Cold") },
    { TR_RES_LITE, _("閃光", "Light") },
};

const std::vector<flag_desc> vulnerable_flags_desc = {
    { TR_VUL_FIRE, _("火炎", "Fire") },
    { TR_VUL_LITE, _("閃光", "Light") },
};

/* Elemental immunities (along with poison) */
const std::vector<flag_desc> immune_flags_desc = {
    { TR_IM_FIRE, _("火炎", "Fire") },
};

/* Sustain stats -  these are given their "own" line in the spoiler file, mainly for simplicity */
const std::vector<flag_desc> sustain_flags_desc = {
    { TR_SUST_STR, _("腕力", "STR") },
    { TR_SUST_CON, _("耐久力", "CON") },
};

/* Miscellaneous magic given by an object's "flags2" field */
const std::vector<flag_desc> misc_flags2_desc = {
    { TR_REFLECT, _("反射", "Reflection") },
    { TR_HOLD_EXP, _("経験値維持", "Hold Experience") },
};

/* Miscellaneous magic given by an object's "flags3" field */
const std::vector<flag_desc> misc_flags3_desc = {
    { TR_SEE_INVIS, _("可視透明", "See Invisible") },
    { TR_TELEPATHY, _("テレパシー", "ESP") },
    { TR_ESP_EVIL, _("邪悪感知", "Sense Evil") },
    /*	{ TR_XTRA_MIGHT, _("強力射撃", "Extra Might") }, */
    // { TR_XTRA_SHOTS, _("追加射撃", "+1 Extra Shot") },
    { TR_DRAIN_EXP, _("経験値吸収", "Drains Experience") },
};

/* テスト用: 本家に新しく追加されたテーブルを模したもの */
const std::vector<flag_desc> new_flags_desc = {
    { TR_NEW_TABLE_FLAG, _("新テーブルのフラグ", "New Table Flag") },
};
