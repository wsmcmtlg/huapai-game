"""
花牌游戏 - 胡数计算模块
完整实现所有牌型的胡数计算规则。

规则来源：花牌游戏开发架构文档v2.0 第六章
"""

from .card import Card
from .melds import (
    MeldType, FanType, CharType, JingSubType, Color,
    JING_CHARS, RED_JING_CHARS, BLACK_JING_CHARS,
    WILD_TARGETS, Meld
)


# ============================================================
# 辅助函数：统计牌组合中的精牌属性
# ============================================================

def _count_jing(cards: list[Card], target_char: str | None = None) -> dict:
    """
    统计牌组合中精牌的数量。
    对于赖子，需指定其通配的字面(target_char)。
    返回: {flower_count, skin_count, wild_count}
    """
    flower = 0
    skin = 0
    wild = 0
    for c in cards:
        if c.is_wild:
            wild += 1
        elif c.char == (target_char or c.char):
            if c.is_flower:
                flower += 1
            elif c.is_skin:
                skin += 1
    return {"flower": flower, "skin": skin, "wild": wild}


def _is_all_red(cards: list[Card]) -> bool:
    """判断一组牌是否全部为红牌"""
    return all(c.color == Color.RED for c in cards)


def _is_all_black(cards: list[Card]) -> bool:
    """判断一组牌是否全部为黑牌"""
    return all(c.color == Color.BLACK for c in cards)


# ============================================================
# 顺子胡数计算
# ============================================================

def calc_sequence_score(cards: list[Card], zhu_jing: str | None = None) -> int:
    """
    计算顺子胡数。
    红牌顺子（上大人、可知礼，全红字）: 基础1胡
    其他顺子: 基础0胡
    精牌加胡: 红精(皮)+1/张, 红精(花)+2/张, 黑精(花)+1/张
    主精翻倍: 如果顺子包含主精字面，胡数x2
    """
    base = 0
    jing_bonus = 0

    # 判断是否为纯红牌顺子
    is_pure_red = _is_all_red(cards)
    has_red_jing = any(c.char in RED_JING_CHARS and not c.is_wild for c in cards)
    has_black_jing = any(c.char in BLACK_JING_CHARS and not c.is_wild for c in cards)

    # 纯红牌顺子（上大人、可知礼）基础1胡
    if is_pure_red and not has_red_jing:
        base = 1

    # 精牌加胡
    for c in cards:
        if c.is_wild:
            # 赖子当作红精，至少按红皮精算
            jing_bonus += 1
        elif c.char in RED_JING_CHARS:
            if c.is_flower:
                jing_bonus += 2
            elif c.is_skin:
                jing_bonus += 1
        elif c.char in BLACK_JING_CHARS:
            if c.is_flower:
                jing_bonus += 1
            # 黑皮精不加

    total = base + jing_bonus

    # 主精翻倍
    if zhu_jing and any(
        (c.char == zhu_jing) or (c.is_wild and zhu_jing in WILD_TARGETS)
        for c in cards
    ):
        total *= 2

    return total


# ============================================================
# 对子胡数计算
# ============================================================

def calc_pen_score(cards: list[Card], zhu_jing: str | None = None) -> int:
    """
    计算对子(碰牌)胡数。
    红牌对子: 基础1胡 + 红花精+2/张 + 红皮精+1/张
    黑牌对子: 基础0胡 + 黑花精+1/张
    主精翻倍
    """
    base = 0
    jing_bonus = 0

    is_red_pair = any(c.is_red and not c.is_wild for c in cards)

    if is_red_pair:
        base = 1
    else:
        base = 0

    for c in cards:
        if c.is_wild:
            jing_bonus += 1  # 赖子当红精至少按皮精算
        elif c.char in RED_JING_CHARS:
            if c.is_flower:
                jing_bonus += 2
            elif c.is_skin:
                jing_bonus += 1
        elif c.char in BLACK_JING_CHARS:
            if c.is_flower:
                jing_bonus += 1

    total = base + jing_bonus

    if zhu_jing and any(
        (c.char == zhu_jing) or (c.is_wild and zhu_jing in WILD_TARGETS)
        for c in cards
    ):
        total *= 2

    return total


# ============================================================
# 坎牌(刻子)胡数计算
# ============================================================

def calc_triplet_score(cards: list[Card], zhu_jing: str | None = None) -> int:
    """
    计算坎牌胡数。
    非精牌: 黑坎1胡, 红坎2胡
    精牌: 按花精/皮精/赖子组合计算
    主精翻倍(红精)
    """
    char = cards[0].char if not cards[0].is_wild else None
    # 确定实际字面
    for c in cards:
        if not c.is_wild:
            char = c.char
            break

    if char is None:
        char = "三"  # 全赖子默认当三

    j = _count_jing(cards, char)

    if char in RED_JING_CHARS:
        # 红精坎牌
        f, s, w = j["flower"], j["skin"], j["wild"]
        if f == 0 and s == 3 and w == 0:
            score = 5   # 三个红皮精
        elif f == 1 and s == 2 and w == 0:
            score = 6   # 两皮一花
        elif f == 2 and s == 1 and w == 0:
            score = 7   # 一皮两花
        elif f == 2 and w == 1 and s == 0:
            score = 9   # 两花一赖
        elif f == 1 and w == 2 and s == 0:
            score = 12  # 一花两赖
        elif w == 3:
            score = 12  # 三赖(按一花两赖)
        else:
            # 混合情况：花精当皮精+赖子的组合
            total_jing = f + s + w
            effective_flower = f + w  # 赖子按花精算
            effective_skin = s
            if effective_flower >= 2:
                score = 12
            elif effective_flower == 1:
                score = 9
            else:
                score = 7

        # 主精翻倍
        if zhu_jing == char:
            score *= 2
        return score

    elif char in BLACK_JING_CHARS:
        # 黑精坎牌
        f, s, w = j["flower"], j["skin"], j["wild"]
        # 黑精坎牌不存在赖子
        if f == 0 and s == 3:
            score = 1   # 三个黑皮精
        elif f == 1 and s == 2:
            score = 2   # 两皮一花
        elif f == 2 and s == 1:
            score = 3   # 一皮两花
        else:
            score = 1
        return score

    else:
        # 非精牌坎牌
        is_red = cards[0].is_red
        score = 2 if is_red else 1
        return score


# ============================================================
# 招牌胡数计算
# ============================================================

def calc_zhao_score(cards: list[Card], zhu_jing: str | None = None) -> int:
    """
    计算招牌胡数。
    """
    char = None
    for c in cards:
        if not c.is_wild:
            char = c.char
            break
    if char is None:
        char = "三"

    j = _count_jing(cards, char)

    if char in RED_JING_CHARS:
        f, s, w = j["flower"], j["skin"], j["wild"]
        if f == 1 and s == 3:
            score = 12  # 三皮一花
        elif f == 2 and s == 2:
            score = 14  # 两皮两花
        elif w >= 1:
            # 含赖子的红精招
            eff_f = f + w
            eff_s = s
            if eff_f == 1 and eff_s == 3:
                score = 12
            elif eff_f == 2 and eff_s == 2:
                score = 14
            else:
                score = 14
        else:
            score = 12

        if zhu_jing == char:
            score *= 2
        return score

    elif char in BLACK_JING_CHARS:
        f, s, w = j["flower"], j["skin"], j["wild"]
        if f == 1 and s == 3:
            score = 3   # 三皮一花
        elif f == 2 and s == 2:
            score = 4   # 两皮两花
        else:
            score = 3
        return score

    else:
        is_red = cards[0].is_red
        return 4 if is_red else 2


# ============================================================
# 扎牌胡数计算
# ============================================================

def calc_zha_score(cards: list[Card], zhu_jing: str | None = None) -> int:
    """
    计算扎牌胡数。
    """
    char = None
    for c in cards:
        if not c.is_wild:
            char = c.char
            break
    if char is None:
        char = "三"

    j = _count_jing(cards, char)

    if char in RED_JING_CHARS:
        f, s, w = j["flower"], j["skin"], j["wild"]
        # 红精扎：按花精/皮精/赖的有效数量分级
        eff_f = f + w  # 赖子按花精算
        eff_s = s
        if eff_s >= 3 and eff_f <= 1:
            score = 12  # 三皮+一花/赖
        elif eff_s == 2 and eff_f == 2:
            score = 14  # 两皮两花/赖
        elif eff_s == 1 and eff_f == 3:
            score = 18  # 一皮三花/赖
        elif eff_f == 4:
            score = 24  # 四花/赖
        else:
            # 按最接近的等级
            if eff_f >= 3:
                score = 18
            elif eff_f >= 2:
                score = 14
            else:
                score = 12

        if zhu_jing == char:
            score *= 2
        return score

    elif char in BLACK_JING_CHARS:
        f, s, w = j["flower"], j["skin"], j["wild"]
        if f == 1 and s == 3:
            score = 3
        elif f == 2 and s == 2:
            score = 4
        else:
            score = 3
        return score

    else:
        is_red = cards[0].is_red
        return 4 if is_red else 2


# ============================================================
# 穿牌胡数计算
# ============================================================

def calc_chuan_score(cards: list[Card], zhu_jing: str | None = None) -> int:
    """计算穿牌胡数。"""
    char = None
    for c in cards:
        if not c.is_wild:
            char = c.char
            break
    if char is None:
        char = "三"

    j = _count_jing(cards, char)

    if char in RED_JING_CHARS:
        f, s, w = j["flower"], j["skin"], j["wild"]
        eff_f = f + w
        eff_s = s
        if eff_s == 3 and eff_f == 2:
            score = 56
        elif eff_s == 2 and eff_f == 3:
            score = 72
        elif eff_s == 1 and eff_f == 4:
            score = 96
        elif eff_f == 5:
            score = 96
        else:
            score = 56
        return score

    elif char in BLACK_JING_CHARS:
        return 6

    else:
        is_red = cards[0].is_red
        return 8 if is_red else 4


# ============================================================
# 泛牌胡数计算
# ============================================================

def calc_fan_score(cards: list[Card], fan_type: FanType,
                   zhu_jing: str | None = None) -> int:
    """
    计算泛牌胡数。
    泛牌胡数与穿牌相同。
    """
    char = None
    for c in cards:
        if not c.is_wild:
            char = c.char
            break
    if char is None:
        char = "三"

    j = _count_jing(cards, char)

    if char in RED_JING_CHARS:
        # 红精泛(无赖子): 28胡
        score = 28
        if zhu_jing == char:
            score *= 2
        return score

    elif char in BLACK_JING_CHARS:
        return 6

    else:
        # 非精泛牌 = 穿牌胡数
        is_red = cards[0].is_red
        return 8 if is_red else 4


# ============================================================
# 统一计算入口
# ============================================================

SCORE_CALCULATORS = {
    MeldType.SEQUENCE: lambda cards, zj: calc_sequence_score(cards, zj),
    MeldType.TRIPLET: lambda cards, zj: calc_triplet_score(cards, zj),
    MeldType.PEN: lambda cards, zj: calc_pen_score(cards, zj),
    MeldType.ZHAO: lambda cards, zj: calc_zhao_score(cards, zj),
    MeldType.ZHA: lambda cards, zj: calc_zha_score(cards, zj),
    MeldType.CHUAN: lambda cards, zj: calc_chuan_score(cards, zj),
}


def calc_meld_score(meld: Meld, zhu_jing: str | None = None) -> int:
    """计算单个牌型的胡数"""
    if meld.meld_type == MeldType.FAN:
        return calc_fan_score(meld.cards, meld.fan_type or FanType.FROM_DISCARD, zhu_jing)
    calc_fn = SCORE_CALCULATORS.get(meld.meld_type)
    if calc_fn:
        return calc_fn(meld.cards, zhu_jing)
    return 0


def calc_total_score(melds: list[Meld], remaining: list[Card] | None = None,
                     zhu_jing: str | None = None) -> int:
    """
    计算总胡数。
    melds: 已确定的牌型列表
    remaining: 未成型的牌（眼或独张，不计算胡数）
    zhu_jing: 主精字面
    """
    total = 0
    for meld in melds:
        total += calc_meld_score(meld, zhu_jing)
    return total


def find_best_zhu_jing(melds: list[Meld],
                       remaining: list[Card] | None = None) -> tuple[str, int]:
    """
    找出最优主精及其对应的最大胡数。
    主精在"三""五""七"中选择使胡数最大的。
    如果没有任何红精牌型，返回(None, score)。
    """
    candidates = ["三", "五", "七"]
    best_char = None
    best_score = 0

    # 先算无主精的分数
    base_score = calc_total_score(melds, remaining, zhu_jing=None)

    for zj in candidates:
        score = calc_total_score(melds, remaining, zhu_jing=zj)
        if score > best_score:
            best_score = score
            best_char = zj

    if best_score <= base_score:
        return (None, base_score)

    return (best_char, best_score)
