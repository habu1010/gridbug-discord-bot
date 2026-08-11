/* テスト用の縮小版 activation-info-table.cpp */
#include "object-enchant/activation-info-table.h"

const std::vector<activation_type> activation_info = {
	{ "SUNLIGHT", TV_NONE, 10, 250, 10, 0, _("太陽光線", "beam of sunlight") },
	{ "LIGHT", TV_NONE, 10, 150, 10, 10, _("イルミネーション", "light area") },
	{ "CURE_1000", TV_NONE, 70, 5000, 888, 0, _("*体力回復*", "restore 1000 hit points") },
	{ "TERROR", TV_NONE, 10, 100, ACTIVATION_TERROR, 0, _("恐慌", "terror") },
	{ "MURAMASA", TV_SWORD, 0, 0, ACTIVATION_MURAMASA, 0, _("腕力上昇", "increase STR") },
	{ "BERSERK", TV_NONE, 33, 400, 0, 0, _("士気高揚と祝福", "heroism and bless") },
	/* 2行に折り返された定義 (prev_line との結合が必要) */
	{ "BR_FIRE", TV_RING, 40,
	  1000, 250, 0, _("火炎のブレス (200)", "breathe fire (200)") },
	{ "DISP_EVIL", TV_NONE, 50, 1000, 300, 0, _("邪悪退散(x5)", "dispel evil (x5)") },
};
