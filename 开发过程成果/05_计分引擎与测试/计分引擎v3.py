"""
core/scoring.py — 胡数计算模块 (v3 — 查表法版)
=================================================
核心改动: 精牌(对/坎/扎/招/穿/泛)计胡全部改为查表法
  - 新增 _JING_HU_TABLE: 精牌胡数速查表(V3.0, 两次实战验证通过)
  - 查表键: (牌型, 皮数, 花数, 赖数, is_main_jin)
  - 顺子/碰牌/非精牌计胡保持公式法(已验证)
  - 同时修复 RED_SEQUENCES 匹配BUG: sorted tuple 可能与原始顺序不同,
    改用 frozenset 归一化比较

速查表数据来源:
  - V3.0反馈版(用户填写, 含红精+黑精全部组合)
  - 第二副实战验证: 主精=七, 105胡
  - 第三副实战验证: 主精=五, 33胡
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from .card import Card
from .melds import (
    CharType, Color, JingSubType, MeldType,
    RED_JING_CHARS, BLACK_JING_CHARS, JING_CHARS,
    WILD_CHAR, WILD_USABLE_CHARS, RED_SEQUENCES, MIN_HU_SCORE,
)


# 归一化: RED_SEQUENCES → frozenset 集合, 避免汉字排序导致 tuple 顺序不匹配
_RED_SEQ_FROZEN: Set[frozenset] = {frozenset(s) for s in RED_SEQUENCES}


@dataclass(frozen=True)
class Meld:
    """牌型（句牌）数据结构"""
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

    def __repr__(self) -> str:
        chars = ",".join(str(c) for c in self.cards)
        open_mark = "[明]" if self.is_open else "[暗]"
        return f"Meld({self.meld_type.value}, [{chars}] {open_mark})"


# ============================================================================
# 精牌胡数速查表 V3.0
# ============================================================================
# 查表键: (皮数, 花数, 赖数) → (非主精胡数, 主精胡数)
# 主精翻倍规律: 主精 = 非主精 × 2 (全部数据均满足)
# 精招 = 精扎 (胡数相同, 暗牌/明牌不影响精牌计胡)
# 精穿 = 精泛 (胡数相同)
# 赖子只能配三五七(红精), 不能配乙九(黑精)
# 每种精牌最多 3皮 + 2花, 赖子全局最多 2张
# ============================================================================

# 红精牌型表: (皮, 花, 赖) → (非主精, 主精)
_RED_JING_PAIR_TABLE: Dict[Tuple[int, int, int], Tuple[int, int]] = {
    (0, 2, 0): (4, 8),    # 2花
    (1, 1, 0): (3, 6),    # 1皮1花
    (2, 0, 0): (2, 4),    # 2皮
}

_RED_JING_KAN_TABLE: Dict[Tuple[int, int, int], Tuple[int, int]] = {
    # 纯精牌(无赖子)
    (1, 2, 0): (7, 14),   # 1皮2花
    (2, 1, 0): (6, 12),   # 2皮1花
    (3, 0, 0): (5, 10),   # 3皮
    # 含赖子(赖=花精, 仅红精三五七)
    (0, 1, 2): (12, 24),  # 1花2赖
    (0, 2, 1): (9, 18),   # 2花1赖
    (1, 0, 2): (7, 14),   # 1皮2赖
    (1, 1, 1): (7, 14),   # 1皮1花1赖
    (2, 0, 1): (6, 12),   # 2皮1赖
}

_RED_JING_ZHA_TABLE: Dict[Tuple[int, int, int], Tuple[int, int]] = {
    # 纯精牌(无赖子), 招牌=扎牌共用
    (2, 2, 0): (14, 28),  # 2皮2花
    (3, 1, 0): (12, 24),  # 3皮1花
    # 含赖子(赖=花精, 仅红精三五七)
    (0, 2, 2): (24, 48),  # 2花2赖
    (1, 1, 2): (18, 36),  # 1皮1花2赖
    (1, 2, 1): (18, 36),  # 1皮2花1赖
    (2, 0, 2): (14, 28),  # 2皮2赖
    (2, 1, 1): (14, 28),  # 2皮1花1赖
    (3, 0, 1): (12, 24),  # 3皮1赖
}

_RED_JING_CHUAN_TABLE: Dict[Tuple[int, int, int], Tuple[int, int]] = {
    # 纯精牌(无赖子), 穿牌=泛牌共用
    (3, 2, 0): (28, 56),  # 3皮2花
    # 含赖子(赖=花精, 仅红精三五七)
    (1, 2, 2): (48, 96),  # 1皮2花2赖
    (2, 1, 2): (36, 72),  # 2皮1花2赖
    (2, 2, 1): (36, 72),  # 2皮2花1赖
    (3, 0, 2): (28, 56),  # 3皮2赖
    (3, 1, 1): (28, 56),  # 3皮1花1赖
}

# 黑精牌型表: (皮, 花) → 胡数
_BLACK_JING_PAIR_TABLE: Dict[Tuple[int, int], int] = {
    (0, 2): 2,    # 2花
    (1, 1): 1,    # 1皮1花
    (2, 0): 0,    # 2皮
}

_BLACK_JING_KAN_TABLE: Dict[Tuple[int, int], int] = {
    (1, 2): 3,    # 1皮2花
    (2, 1): 2,    # 2皮1花
    (3, 0): 1,    # 3皮
}

_BLACK_JING_ZHA_TABLE: Dict[Tuple[int, int], int] = {
    (2, 2): 4,    # 2皮2花
    (3, 1): 3,    # 3皮1花
}

_BLACK_JING_CHUAN_TABLE: Dict[Tuple[int, int], int] = {
    (3, 2): 6,    # 3皮2花
}


class ScoreCalculator:
    """胡数计算器（v3 — 精牌查表法版）"""

    # ========== 辅助方法 ==========

    @staticmethod
    def _classify_cards(cards: Tuple[Card, ...]) -> Dict[str, int]:
        """统计牌型中各类牌的数量
        返回: {skin: N, red_flower: N, black_flower: N, wild: N, normal: N}
        """
        skin = 0
        red_flower = 0
        black_flower = 0
        wild = 0
        normal = 0

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

        return {
            "skin": skin, "red_flower": red_flower,
            "black_flower": black_flower, "wild": wild, "normal": normal,
        }

    @staticmethod
    def _has_jing(cards: Tuple[Card, ...]) -> Tuple[bool, bool, bool]:
        """检查牌型中是否含精牌
        返回: (has_any_jing, has_red_jing, has_black_jing)
        """
        has_red = any(c.is_jin and c.char in RED_JING_CHARS for c in cards)
        has_black = any(c.is_jin and c.char in BLACK_JING_CHARS for c in cards)
        return (has_red or has_black, has_red, has_black)

    @staticmethod
    def _is_all_red(cards: Tuple[Card, ...]) -> bool:
        """是否全为红牌字面（不含精牌属性判断）"""
        return all(c.color == Color.RED for c in cards)

    @staticmethod
    def _wild_hu_per_card(is_main_jin: bool) -> int:
        """赖子单张计胡: 普通+2, 主精+4"""
        return 4 if is_main_jin else 2

    # ========== 精牌查表核心方法 ==========

    def _lookup_jing_hu(
        self, cards: Tuple[Card, ...], is_main_jin: bool = False
    ) -> Optional[int]:
        """精牌组合查表计胡

        统计皮/花/赖数量, 根据红精/黑精查对应表。
        返回: 胡数, 或 None(非精牌组合)
        """
        cl = self._classify_cards(cards)
        skin = cl["skin"]
        red_flower = cl["red_flower"]
        black_flower = cl["black_flower"]
        wild = cl["wild"]
        n = len(cards)

        # 确定牌型类别(张数)
        if n == 2:
            table_type = "pair"
        elif n == 3:
            table_type = "kan"
        elif n == 4:
            table_type = "zha"   # 招牌=扎牌共用
        elif n == 5:
            table_type = "chuan" # 穿牌=泛牌共用
        else:
            return None

        has_any, has_red, has_black = self._has_jing(cards)
        if not has_any:
            return None

        if has_red:
            return self._lookup_red_jing(
                table_type, skin, red_flower, wild, is_main_jin
            )
        elif has_black:
            return self._lookup_black_jing(
                table_type, skin, black_flower, is_main_jin
            )
        return None

    @staticmethod
    def _lookup_red_jing(
        table_type: str, skin: int, flower: int, wild: int,
        is_main_jin: bool
    ) -> int:
        """红精查表"""
        key = (skin, flower, wild)
        table = None
        if table_type == "pair":
            table = _RED_JING_PAIR_TABLE
        elif table_type == "kan":
            table = _RED_JING_KAN_TABLE
        elif table_type == "zha":
            table = _RED_JING_ZHA_TABLE
        elif table_type == "chuan":
            table = _RED_JING_CHUAN_TABLE

        if table and key in table:
            nmj, mj = table[key]
            return mj if is_main_jin else nmj
        return 0

    @staticmethod
    def _lookup_black_jing(
        table_type: str, skin: int, flower: int,
        is_main_jin: bool
    ) -> int:
        """黑精查表(无赖子参与)"""
        key = (skin, flower)
        table = None
        if table_type == "pair":
            table = _BLACK_JING_PAIR_TABLE
        elif table_type == "kan":
            table = _BLACK_JING_KAN_TABLE
        elif table_type == "zha":
            table = _BLACK_JING_ZHA_TABLE
        elif table_type == "chuan":
            table = _BLACK_JING_CHUAN_TABLE

        if table and key in table:
            hu = table[key]
            if is_main_jin:
                hu *= 2
            return hu
        return 0

    # ========== 顺子计胡(公式法, 已验证) ==========

    def calc_sequence_hu(
        self, cards: Tuple[Card, ...], chars: Tuple[str, ...],
        is_main_jin: bool = False,
    ) -> int:
        """计算顺子胡数

        红牌顺子（上大人、可知礼）：基础1胡
        其他顺子：基础0胡
        精牌加成:
          红精皮 +1胡/张，红精花 +2胡/张
          黑精皮 +0胡/张，黑精花 +1胡/张
          赖子   +2胡/张，主精赖子 +4胡/张
        """
        # 用 frozenset 归一化比较, 避免 sorted() 汉字排序与原始顺序不同
        chars_set = frozenset(chars)
        is_red_seq = chars_set in _RED_SEQ_FROZEN
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

    # ========== 对子(眼)计胡(查表法) ==========

    def calc_pair_hu(self, cards: Tuple[Card, ...], is_main_jin: bool = False) -> int:
        """计算对子(眼)胡数 — 查表法

        精牌对子查 _RED_JING_PAIR_TABLE / _BLACK_JING_PAIR_TABLE
        赖子对子: +2/张, 主精赖子+4/张
        非精牌对子: 0胡
        """
        # 赖子对子
        wild_count = sum(1 for c in cards if c.is_wild)
        if wild_count == 2:
            return 2 * self._wild_hu_per_card(is_main_jin)

        # 精牌对子 → 查表
        has_any, _, _ = self._has_jing(cards)
        if has_any:
            return self._lookup_jing_hu(cards, is_main_jin) or 0

        return 0

    # ========== 碰牌计胡(公式法, 已验证) ==========

    def calc_pen_hu(self, cards: Tuple[Card, ...]) -> int:
        """计算碰牌(3张明牌)胡数

        碰牌: 手中2张 + 旁家1张 = 明牌区, 已失自由度
        红牌碰: 基础1胡
        黑牌碰: 基础0胡
        含精牌加成(花精/皮精): 每张花精+1, 每张皮精+1
          注: 碰牌中精牌加成不分红黑, 花精皮精都+1
        赖子: +2/张(红花精处理)
        """
        first_non_wild = None
        for c in cards:
            if not c.is_wild:
                first_non_wild = c
                break

        if first_non_wild is None:
            return 0

        is_red_pen = (first_non_wild.color == Color.RED)
        base = 1 if is_red_pen else 0

        bonus = 0
        for c in cards:
            if c.is_wild:
                bonus += 2
            elif c.is_jin:
                bonus += 1

        return base + bonus

    # ========== 坎牌计胡(查表法) ==========

    def calc_kan_hu(self, cards: Tuple[Card, ...], is_main_jin: bool = False) -> int:
        """计算坎牌（3张暗牌，手牌区）胡数 — 查表法

        精牌坎 → 查表(已含主精翻倍)
        非精牌: 红牌2胡, 黑牌1胡
        """
        hu = self._lookup_jing_hu(cards, is_main_jin)
        if hu is not None:
            return hu

        # 非精牌
        if self._is_all_red(cards):
            return 2
        else:
            return 1

    # ========== 招牌计胡(查表法) ==========

    def calc_zhao_hu(self, cards: Tuple[Card, ...], is_main_jin: bool = False) -> int:
        """计算招牌（4张明牌）胡数 — 查表法

        精牌招 → 查表(已含主精翻倍)
        非精牌: 红牌4胡, 黑牌2胡
        """
        hu = self._lookup_jing_hu(cards, is_main_jin)
        if hu is not None:
            return hu

        if self._is_all_red(cards):
            return 4
        else:
            return 2

    # ========== 扎牌计胡(查表法) ==========

    def calc_zha_hu(self, cards: Tuple[Card, ...], is_main_jin: bool = False) -> int:
        """计算扎牌（4张暗牌）胡数 — 查表法

        扎牌与招牌查同一张表(胡数相同)
        """
        return self.calc_zhao_hu(cards, is_main_jin)

    # ========== 穿牌/泛牌计胡(查表法) ==========

    def calc_chuan_hu(self, cards: Tuple[Card, ...], is_main_jin: bool = False) -> int:
        """计算穿牌（5张明牌）胡数 — 查表法

        精牌穿 → 查表(已含主精翻倍)
        非精牌: 红牌5胡, 黑牌3胡
        """
        hu = self._lookup_jing_hu(cards, is_main_jin)
        if hu is not None:
            return hu

        if self._is_all_red(cards):
            return 5
        else:
            return 3

    def calc_fan_hu(self, cards: Tuple[Card, ...], is_main_jin: bool = False) -> int:
        """计算泛牌（5张暗牌）胡数 — 查表法

        泛牌与穿牌查同一张表(胡数相同)
        """
        return self.calc_chuan_hu(cards, is_main_jin)

    # ========== 主精选择 ==========

    def find_best_main_jin(self, melds: List[Meld]) -> Optional[str]:
        """选择使总胡数最高的主精

        遍历所有精牌字面(包括眼中的), 选择使翻倍后总胡数最高的
        """
        if not melds:
            return None

        all_jing_chars = set()
        for m in melds:
            for c in m.cards:
                if c.char in JING_CHARS:
                    all_jing_chars.add(c.char)

        if not all_jing_chars:
            return None

        best_char = None
        best_hu = 0

        for jin_char in all_jing_chars:
            hu = self.calculate_hand_hu(melds, main_jin=jin_char)

            if hu > best_hu:
                best_hu = hu
                best_char = jin_char

        return best_char

    # ========== 整手计胡 ==========

    def calculate_hand_hu(
        self, melds: List[Meld], main_jin: Optional[str] = None
    ) -> int:
        """计算整手牌的总胡数

        精牌组合: 查表法, is_main_jin直接传入各calc函数, 表中已含主精翻倍
        顺子/碰牌: 公式法, 精牌加成在函数内部处理
        非精牌坎/招/扎/穿/泛: is_main_jin传入, 但非精牌不受主精影响
        """
        total = 0

        for m in melds:
            has_main = main_jin and any(c.char == main_jin for c in m.cards)

            if m.meld_type == MeldType.PAIR:
                total += self.calc_pair_hu(m.cards, is_main_jin=has_main)
                continue

            chars = tuple(sorted(c.char for c in m.cards if not c.is_wild))

            if m.meld_type == MeldType.SEQUENCE:
                hu = self.calc_sequence_hu(m.cards, chars, is_main_jin=has_main)
            elif m.meld_type == MeldType.KAN:
                hu = self.calc_kan_hu(m.cards, is_main_jin=has_main)
            elif m.meld_type == MeldType.PEN:
                hu = self.calc_pen_hu(m.cards)
            elif m.meld_type == MeldType.ZHAO:
                hu = self.calc_zhao_hu(m.cards, is_main_jin=has_main)
            elif m.meld_type == MeldType.ZHA:
                hu = self.calc_zha_hu(m.cards, is_main_jin=has_main)
            elif m.meld_type in (MeldType.CHUAN, MeldType.FAN):
                hu = self.calc_chuan_hu(m.cards, is_main_jin=has_main)
            else:
                hu = 0

            total += hu

        return total
