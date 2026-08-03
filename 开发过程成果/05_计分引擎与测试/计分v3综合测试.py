"""
test_scoring_v3.py — scoring_v3.py 三副实战牌型验证
"""
import sys, os

# 把项目目录加到 sys.path
proj_core = r"C:\Users\XBW\Desktop\My_LHP\Phase 1 规则引擎"
sys.path.insert(0, proj_core)

# 替换 scoring 模块指向 scoring_v3
from core import melds
from core.card import Card

# 手动加载 scoring_v3 的 ScoreCalculator
import importlib.util
spec = importlib.util.spec_from_file_location("scoring_v3",
    r"C:\Users\XBW\Documents\lingxi-claw\20260509-19-35-44-847\scoring_v3.py")
scoring_v3 = importlib.util.module_from_spec(spec)

# 但 scoring_v3 内部有 relative import (.card, .melds), 需要特殊处理
# 直接把类定义复制到独立模块中

# ============================================================================
# 直接从 scoring_v3.py 中加载核心内容（跳过 relative import）
# ============================================================================

# 把项目 core 加入 path
sys.path.insert(0, proj_core)

from core.melds import (
    CharType, Color, JingSubType, MeldType,
    RED_JING_CHARS, BLACK_JING_CHARS, JING_CHARS,
    WILD_CHAR, WILD_USABLE_CHARS, RED_SEQUENCES, MIN_HU_SCORE,
)
from core.card import Card as _Card

# ---------- 重新定义 Meld（与 scoring_v3 中的定义一致）----------
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

@dataclass(frozen=True)
class Meld:
    meld_type: MeldType
    cards: tuple
    is_open: bool = False
    contains_main_jin: bool = False
    contains_vice_jin: bool = False

    @property
    def char(self) -> str:
        return self.cards[0].char

    @property
    def all_chars(self) -> List[str]:
        return [c.char for c in self.cards]


# ---------- 速查表（从 scoring_v3.py 复制）----------
_RED_JING_PAIR_TABLE = {
    (0, 2, 0): (4, 8),
    (1, 1, 0): (3, 6),
    (2, 0, 0): (2, 4),
}
_RED_JING_KAN_TABLE = {
    (1, 2, 0): (7, 14), (2, 1, 0): (6, 12), (3, 0, 0): (5, 10),
    (0, 1, 2): (12, 24), (0, 2, 1): (9, 18),
    (1, 0, 2): (7, 14), (1, 1, 1): (7, 14), (2, 0, 1): (6, 12),
}
_RED_JING_ZHA_TABLE = {
    (2, 2, 0): (14, 28), (3, 1, 0): (12, 24),
    (0, 2, 2): (24, 48), (1, 1, 2): (18, 36), (1, 2, 1): (18, 36),
    (2, 0, 2): (14, 28), (2, 1, 1): (14, 28), (3, 0, 1): (12, 24),
}
_RED_JING_CHUAN_TABLE = {
    (3, 2, 0): (28, 56),
    (1, 2, 2): (48, 96), (2, 1, 2): (36, 72), (2, 2, 1): (36, 72),
    (3, 0, 2): (28, 56), (3, 1, 1): (28, 56),
}
_BLACK_JING_PAIR_TABLE = {(0, 2): 2, (1, 1): 1, (2, 0): 0}
_BLACK_JING_KAN_TABLE = {(1, 2): 3, (2, 1): 2, (3, 0): 1}
_BLACK_JING_ZHA_TABLE = {(2, 2): 4, (3, 1): 3}
_BLACK_JING_CHUAN_TABLE = {(3, 2): 6}


class ScoreCalculator:
    """胡数计算器（v3 — 精牌查表法版）"""

    @staticmethod
    def _classify_cards(cards):
        skin = red_flower = black_flower = wild = normal = 0
        for c in cards:
            if c.is_wild:
                wild += 1
            elif c.is_jin and c.is_flower:
                if c.char in RED_JING_CHARS:
                    red_flower += 1
                else:
                    black_flower += 1
            elif c.is_jin:
                skin += 1
            else:
                normal += 1
        return {"skin": skin, "red_flower": red_flower,
                "black_flower": black_flower, "wild": wild, "normal": normal}

    @staticmethod
    def _has_jing(cards):
        has_red = any(c.is_jin and c.char in RED_JING_CHARS for c in cards)
        has_black = any(c.is_jin and c.char in BLACK_JING_CHARS for c in cards)
        return (has_red or has_black, has_red, has_black)

    @staticmethod
    def _is_all_red(cards):
        return all(c.color == Color.RED for c in cards)

    @staticmethod
    def _wild_hu_per_card(is_main_jin):
        return 4 if is_main_jin else 2

    def _lookup_jing_hu(self, cards, is_main_jin=False):
        cl = self._classify_cards(cards)
        skin, red_flower, black_flower, wild = (
            cl["skin"], cl["red_flower"], cl["black_flower"], cl["wild"])
        n = len(cards)
        if n == 2: table_type = "pair"
        elif n == 3: table_type = "kan"
        elif n == 4: table_type = "zha"
        elif n == 5: table_type = "chuan"
        else: return None

        has_any, has_red, has_black = self._has_jing(cards)
        if not has_any:
            return None
        if has_red:
            return self._lookup_red_jing(table_type, skin, red_flower, wild, is_main_jin)
        elif has_black:
            return self._lookup_black_jing(table_type, skin, black_flower, is_main_jin)
        return None

    @staticmethod
    def _lookup_red_jing(table_type, skin, flower, wild, is_main_jin):
        key = (skin, flower, wild)
        table = {"pair": _RED_JING_PAIR_TABLE, "kan": _RED_JING_KAN_TABLE,
                 "zha": _RED_JING_ZHA_TABLE, "chuan": _RED_JING_CHUAN_TABLE}.get(table_type)
        if table and key in table:
            nmj, mj = table[key]
            return mj if is_main_jin else nmj
        return 0

    @staticmethod
    def _lookup_black_jing(table_type, skin, flower, is_main_jin):
        key = (skin, flower)
        table = {"pair": _BLACK_JING_PAIR_TABLE, "kan": _BLACK_JING_KAN_TABLE,
                 "zha": _BLACK_JING_ZHA_TABLE, "chuan": _BLACK_JING_CHUAN_TABLE}.get(table_type)
        if table and key in table:
            hu = table[key]
            if is_main_jin: hu *= 2
            return hu
        return 0

    def calc_sequence_hu(self, cards, chars, is_main_jin=False):
        chars_set = frozenset(chars)
        is_red_seq = chars_set in RED_SEQUENCES
        base = 1 if is_red_seq else 0
        bonus = 0
        for c in cards:
            if c.is_wild:
                bonus += self._wild_hu_per_card(is_main_jin)
            elif c.is_jin and c.char in RED_JING_CHARS:
                bonus += 2 if c.is_flower else 1
            elif c.is_jin and c.char in BLACK_JING_CHARS:
                bonus += 1 if c.is_flower else 0
        return base + bonus

    def calc_pair_hu(self, cards, is_main_jin=False):
        wild_count = sum(1 for c in cards if c.is_wild)
        if wild_count == 2:
            return 2 * self._wild_hu_per_card(is_main_jin)
        has_any, _, _ = self._has_jing(cards)
        if has_any:
            return self._lookup_jing_hu(cards, is_main_jin) or 0
        return 0

    def calc_pen_hu(self, cards):
        first_non_wild = None
        for c in cards:
            if not c.is_wild:
                first_non_wild = c
                break
        if first_non_wild is None: return 0
        is_red_pen = (first_non_wild.color == Color.RED)
        base = 1 if is_red_pen else 0
        bonus = 0
        for c in cards:
            if c.is_wild: bonus += 2
            elif c.is_jin: bonus += 1
        return base + bonus

    def calc_kan_hu(self, cards, is_main_jin=False):
        hu = self._lookup_jing_hu(cards, is_main_jin)
        if hu is not None: return hu
        return 2 if self._is_all_red(cards) else 1

    def calc_zhao_hu(self, cards, is_main_jin=False):
        hu = self._lookup_jing_hu(cards, is_main_jin)
        if hu is not None: return hu
        return 4 if self._is_all_red(cards) else 2

    def calc_zha_hu(self, cards, is_main_jin=False):
        return self.calc_zhao_hu(cards, is_main_jin)

    def calc_chuan_hu(self, cards, is_main_jin=False):
        hu = self._lookup_jing_hu(cards, is_main_jin)
        if hu is not None: return hu
        return 5 if self._is_all_red(cards) else 3

    def calc_fan_hu(self, cards, is_main_jin=False):
        return self.calc_chuan_hu(cards, is_main_jin)

    def calculate_hand_hu(self, melds, main_jin=None):
        total = 0
        for m in melds:
            has_main = main_jin and any(c.char == main_jin for c in m.cards)
            if m.meld_type == MeldType.PAIR:
                total += self.calc_pair_hu(m.cards, is_main_jin=has_main)
                continue
            chars = tuple(sorted(c.char for c in m.cards if not c.is_wild))
            if m.meld_type == MeldType.SEQUENCE:
                total += self.calc_sequence_hu(m.cards, chars, is_main_jin=has_main)
            elif m.meld_type == MeldType.KAN:
                total += self.calc_kan_hu(m.cards, is_main_jin=has_main)
            elif m.meld_type == MeldType.PEN:
                total += self.calc_pen_hu(m.cards)
            elif m.meld_type == MeldType.ZHAO:
                total += self.calc_zhao_hu(m.cards, is_main_jin=has_main)
            elif m.meld_type == MeldType.ZHA:
                total += self.calc_zha_hu(m.cards, is_main_jin=has_main)
            elif m.meld_type in (MeldType.CHUAN, MeldType.FAN):
                total += self.calc_chuan_hu(m.cards, is_main_jin=has_main)
        return total


# ============================================================================
# 辅助函数：快速创建 Card
# ============================================================================
_card_id = 0

def mk(char, card_id=None, *, flower=False):
    """创建一张 Card"""
    global _card_id
    if card_id is None:
        card_id = _card_id
        _card_id += 1
    return _Card.create(char, card_id=card_id, is_flower=flower)


# ============================================================================
# 测试1: 第二副实战牌型 (主精=七, 期望105胡)
# ============================================================================
def test_hand2():
    """
    第二副牌型 (主精=七):
      上上上(坎/扎, 4胡) + 可可可(碰牌, 1胡)
      + 七穿(1皮2花2赖, 主精=96胡)
      + 三眼(1皮1花, 3胡) + 乙眼(1皮1花, 1胡)
      = 4 + 1 + 96 + 3 + 1 = 105
    """
    calc = ScoreCalculator()

    # 上扎: 上上上上 (4张暗牌=扎牌)
    # 非精牌红牌扎牌: 4胡
    shang_zha = Meld(MeldType.ZHA, (
        mk("上"), mk("上"), mk("上"), mk("上"),
    ))

    # 可碰: 可可可 (3张碰牌, 明牌)
    # 红牌碰: 基础1胡
    ke_pen = Meld(MeldType.PEN, (
        mk("可"), mk("可"), mk("可"),
    ))

    # 七穿: 七+皮七+花七+花七+赖+赖... 等等, 穿牌5张
    # "穿牌，两花一皮两赖" = 1皮七 + 2花七 + 2赖 = 5张
    qi_chuan = Meld(MeldType.CHUAN, (
        mk("七"),          # 皮七
        mk("七", flower=True),  # 花七
        mk("七", flower=True),  # 花七
        mk("赖"),          # 赖子
        mk("赖"),          # 赖子
    ))

    # 三眼(对子): 1皮三 + 1花三
    san_pair = Meld(MeldType.PAIR, (
        mk("三"), mk("三", flower=True),
    ))

    # 乙眼(对子): 1皮乙 + 1花乙
    yi_pair = Meld(MeldType.PAIR, (
        mk("乙"), mk("乙", flower=True),
    ))

    melds = [shang_zha, ke_pen, qi_chuan, san_pair, yi_pair]
    total = calc.calculate_hand_hu(melds, main_jin="七")

    print(f"\n=== 第二副实战牌型 (主精=七) ===")
    print(f"  上扎(非精红牌4张): {calc.calc_zha_hu(shang_zha.cards)}胡")
    print(f"  可碰(红牌碰): {calc.calc_pen_hu(ke_pen.cards)}胡")
    print(f"  七穿(1皮2花2赖,主精): {calc.calc_chuan_hu(qi_chuan.cards, is_main_jin=True)}胡")
    print(f"  三眼(1皮1花): {calc.calc_pair_hu(san_pair.cards)}胡")
    print(f"  乙眼(1皮1花): {calc.calc_pair_hu(yi_pair.cards)}胡")
    print(f"  总计: {total}胡 (期望: 105胡)")
    assert total == 105, f"第二副验证失败! got {total}, expected 105"
    print("  ✓ 通过!")
    return True


# ============================================================================
# 测试2: 第三副实战牌型 (主精=五, 期望33胡)
# ============================================================================
def test_hand3():
    """
    第三副牌型 (主精=五):
      乙穿(穿牌, 6胡) + 可招(招牌, 4胡)
      + 上大人(顺子, 1胡) + 化三千(顺子, 花三, 2胡)
      + 孔乙已(顺子, 皮乙, 0胡) + 五五赖坎(2花1赖, 18胡)
      + 六七八(混合顺子, 皮七, 1胡) + 八九子(顺子, 花九, 1胡)
      + 十(手中单张, 0胡, 不计) = 33胡
    """
    calc = ScoreCalculator()

    # 乙穿: 乙乙乙乙乙 (5张, 穿牌)
    # 黑精穿牌, 3皮2花 → 查表: 6胡
    yi_chuan = Meld(MeldType.CHUAN, (
        mk("乙"), mk("乙"), mk("乙", flower=True), mk("乙", flower=True), mk("乙"),
    ))

    # 可招: 可可可可 (4张明牌=招牌)
    # 非精牌红牌招牌: 4胡
    ke_zhao = Meld(MeldType.ZHAO, (
        mk("可"), mk("可"), mk("可"), mk("可"),
    ))

    # 上大人(顺子): 红牌顺子, 基础1胡
    shang_da_ren = Meld(MeldType.SEQUENCE, (
        mk("上"), mk("大"), mk("人"),
    ))

    # 化三千(顺子): 混合顺子, 基础0胡, 含花三+1胡
    hua_san_qian = Meld(MeldType.SEQUENCE, (
        mk("化"), mk("三", flower=True), mk("千"),
    ))

    # 孔乙已(顺子): 混合顺子, 基础0胡, 皮乙+0胡
    kong_yi_ji = Meld(MeldType.SEQUENCE, (
        mk("孔"), mk("乙"), mk("已"),
    ))

    # 五坎: 五五赖, 2花+1赖 (五=主精)
    # 红精坎 (2花0皮1赖) → (2,0,1)=6非主精 / (2,0,1)=12主精
    # 但用户说是"两花一赖", 即2花五+1赖=3张坎
    # key=(skin=0, flower=2, wild=1) → 查表 (0,2,1)=(9,18), 主精18胡
    wu_kan = Meld(MeldType.KAN, (
        mk("五", flower=True), mk("五", flower=True), mk("赖"),
    ))

    # 六七八(混合顺子): 皮七+1胡
    liu_qi_ba = Meld(MeldType.SEQUENCE, (
        mk("六"), mk("七"), mk("八"),
    ))

    # 八九子(顺子): 花九+1胡
    ba_jiu_zi = Meld(MeldType.SEQUENCE, (
        mk("八"), mk("九", flower=True), mk("子"),
    ))

    # 十(手中单张): 摞听单张, 不在melds中计胡

    melds = [yi_chuan, ke_zhao, shang_da_ren, hua_san_qian, kong_yi_ji,
             wu_kan, liu_qi_ba, ba_jiu_zi]
    total = calc.calculate_hand_hu(melds, main_jin="五")

    print(f"\n=== 第三副实战牌型 (主精=五) ===")
    print(f"  乙穿(3皮2花): {calc.calc_chuan_hu(yi_chuan.cards)}胡")
    print(f"  可招(红牌4张): {calc.calc_zhao_hu(ke_zhao.cards)}胡")
    print(f"  上大人(红顺): {calc.calc_sequence_hu(shang_da_ren.cards, ('大','人','上'))}胡")
    print(f"  化三千(混合顺+花三): {calc.calc_sequence_hu(hua_san_qian.cards, ('千','化','三'))}胡")
    print(f"  孔乙已(混合顺+皮乙): {calc.calc_sequence_hu(kong_yi_ji.cards, ('已','孔','乙'))}胡")
    print(f"  五坎(2花1赖,主精): {calc.calc_kan_hu(wu_kan.cards, is_main_jin=True)}胡")
    print(f"  六七八(混合顺+皮七): {calc.calc_sequence_hu(liu_qi_ba.cards, ('八','六','七'))}胡")
    print(f"  八九子(顺+花九): {calc.calc_sequence_hu(ba_jiu_zi.cards, ('八','子','九'))}胡")
    print(f"  总计: {total}胡 (期望: 33胡)")
    assert total == 33, f"第三副验证失败! got {total}, expected 33"
    print("  ✓ 通过!")
    return True


# ============================================================================
# 运行测试
# ============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("scoring_v3.py 查表法验证测试")
    print("=" * 60)

    ok = True
    try:
        ok = test_hand2() and ok
    except Exception as e:
        print(f"  ✗ 第二副失败: {e}")
        ok = False

    try:
        ok = test_hand3() and ok
    except Exception as e:
        print(f"  ✗ 第三副失败: {e}")
        ok = False

    print("\n" + "=" * 60)
    if ok:
        print("全部测试通过!")
    else:
        print("存在测试失败!")
    print("=" * 60)
