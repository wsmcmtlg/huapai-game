"""
花牌游戏 - 手牌分析器
负责听牌检测、牌型组合枚举、有效操作判断。
"""

from collections import Counter
from .card import Card, cards_to_char_list, sort_cards
from .melds import (
    MeldType, FanType, CharType, JingSubType, Color,
    ALL_SEQUENCES, SEQUENCE_SET, JING_CHARS, RED_JING_CHARS,
    BLACK_JING_CHARS, WILD_TARGETS, Meld
)
from .scoring import calc_total_score, find_best_zhu_jing


# ============================================================
# 牌型组合枚举
# ============================================================

def _get_char_counter(cards: list[Card]) -> Counter:
    """获取牌的字面计数"""
    return Counter(c.char for c in cards)


def _find_triplets(counter: Counter) -> list[tuple[str, int]]:
    """找出所有可能的坎牌（>=3张相同字面）"""
    triplets = []
    for char, count in counter.items():
        if count >= 3:
            triplets.append((char, count))
    return triplets


def _find_sequences(counter: Counter) -> list[tuple]:
    """找出所有可能的顺子"""
    sequences = []
    for seq in ALL_SEQUENCES:
        chars_needed = list(set(seq))  # 去重（顺子中无重复字面）
        if all(counter.get(c, 0) > 0 for c in chars_needed):
            sequences.append(seq)
    return sequences


def _can_form_melds(cards: list[Card], num_melds_needed: int) -> list[list[Meld]]:
    """
    尝试将牌组合成指定数量的牌型。
    返回所有可能的牌型组合列表。
    用于听牌检测。
    """
    results = []
    counter = _get_char_counter(cards)
    _enum_melds(counter, [], num_melds_needed, cards, results)
    return results


def _enum_melds(counter: Counter, current_melds: list, needed: int,
                all_cards: list[Card], results: list):
    """递归枚举所有可能的牌型组合"""
    if needed == 0:
        # 检查是否所有牌都已使用
        if all(v == 0 for v in counter.values()):
            results.append(current_melds[:])
        return

    if needed < 0:
        return

    # 获取当前可用字面
    available = [(c, n) for c, n in counter.items() if n > 0]
    if not available:
        return

    for char, count in available:
        # 尝试顺子
        for seq in ALL_SEQUENCES:
            if char in seq:
                seq_chars = list(seq)
                seq_unique = list(set(seq_chars))
                if all(counter.get(c, 0) > 0 for c in seq_unique):
                    # 执行顺子
                    for c in seq_unique:
                        counter[c] -= 1
                    # 获取对应的牌
                    meld_cards = []
                    temp_counter = Counter()
                    for c in seq_chars:
                        if temp_counter[c] < 1:
                            for card in all_cards:
                                if card.char == c and card not in meld_cards:
                                    meld_cards.append(card)
                                    temp_counter[c] += 1
                                    break
                    meld = Meld(MeldType.SEQUENCE, seq[0], meld_cards)
                    current_melds.append(meld)
                    _enum_melds(counter, current_melds, needed - 1, all_cards, results)
                    current_melds.pop()
                    for c in seq_unique:
                        counter[c] += 1

        # 尝试坎牌/扎牌/穿牌
        if count >= 5:
            # 穿牌（5张）
            char_cards = [c for c in all_cards if c.char == char][:5]
            counter[char] -= 5
            meld = Meld(MeldType.CHUAN, char, char_cards)
            current_melds.append(meld)
            _enum_melds(counter, current_melds, needed - 1, all_cards, results)
            current_melds.pop()
            counter[char] += 5

        if count >= 4:
            # 扎牌（4张）
            char_cards = [c for c in all_cards if c.char == char][:4]
            counter[char] -= 4
            meld = Meld(MeldType.ZHA, char, char_cards)
            current_melds.append(meld)
            _enum_melds(counter, current_melds, needed - 1, all_cards, results)
            current_melds.pop()
            counter[char] += 4

        if count >= 3:
            # 坎牌（3张）
            char_cards = [c for c in all_cards if c.char == char][:3]
            counter[char] -= 3
            meld = Meld(MeldType.TRIPLET, char, char_cards)
            current_melds.append(meld)
            _enum_melds(counter, current_melds, needed - 1, all_cards, results)
            current_melds.pop()
            counter[char] += 3

        break  # 每层只尝试第一个可用字面，避免重复


# ============================================================
# 听牌检测
# ============================================================

def check_ting(cards: list[Card]) -> dict:
    """
    检测是否满足听牌条件。
    
    返回:
    {
        "is_ting": bool,        # 是否听牌
        "ting_type": str|null,  # "两听" or "撂听"
        "best_score": int,      # 最大胡数
        "zhu_jing": str|null,   # 最优主精
        "best_melds": list,     # 最优牌型组合
    }
    
    听牌条件:
    - 撂听: 8个完整牌型 + 1张独张
    - 两听: 7个完整牌型 + 2张(眼)
    - 总胡数 >= 17
    """
    total_cards = len(cards)
    if total_cards < 24 or total_cards > 26:
        return {"is_ting": False, "ting_type": None, "best_score": 0,
                "zhu_jing": None, "best_melds": []}

    best_result = {
        "is_ting": False, "ting_type": None, "best_score": 0,
        "zhu_jing": None, "best_melds": []
    }

    # 撂听: 8个完整牌型 + 1张独张 (25张手牌)
    if total_cards == 25:
        _check_liao_ting(cards, best_result)

    # 两听: 7个完整牌型 + 2张(眼) (25或26张)
    if total_cards >= 25:
        _check_liang_ting(cards, best_result)

    return best_result


def _check_liao_ting(cards: list[Card], best_result: dict):
    """撂听检测: 8个牌型 + 1张独张"""
    for i, card in enumerate(cards):
        remaining = [c for j, c in enumerate(cards) if j != i]
        melds_list = _can_form_melds(remaining, 8)
        for melds in melds_list:
            zj, score = find_best_zhu_jing(melds)
            if score >= 17 and score > best_result["best_score"]:
                best_result.update({
                    "is_ting": True, "ting_type": "撂听",
                    "best_score": score, "zhu_jing": zj,
                    "best_melds": melds
                })


def _check_liang_ting(cards: list[Card], best_result: dict):
    """两听检测: 7个牌型 + 1对(眼)"""
    counter = _get_char_counter(cards)
    # 找出所有可能的对子
    pairs = [(c, n) for c, n in counter.items() if n >= 2]

    for pair_char, pair_count in pairs:
        # 取出2张作为眼
        remaining_chars = dict(counter)
        remaining_chars[pair_char] -= 2

        remaining_cards = []
        removed = 0
        for c in cards:
            if c.char == pair_char and removed < 2:
                removed += 1
                continue
            remaining_cards.append(c)

        melds_list = _can_form_melds(remaining_cards, 7)
        for melds in melds_list:
            zj, score = find_best_zhu_jing(melds)
            if score >= 17 and score > best_result["best_score"]:
                best_result.update({
                    "is_ting": True, "ting_type": "两听",
                    "best_score": score, "zhu_jing": zj,
                    "best_melds": melds
                })


# ============================================================
# 有效操作判断
# ============================================================

def can_pen(hand_cards: list[Card], discarded_char: str) -> bool:
    """判断是否可以碰牌（对牌）"""
    if discarded_char == "赖":
        return False  # 赖子不能被碰
    count = sum(1 for c in hand_cards if c.char == discarded_char)
    return count >= 2


def can_zhao(hand_cards: list[Card], hidden_melds: list[Meld],
             discarded_char: str) -> bool:
    """判断是否可以招牌（坎牌+旁家打出相同字面）"""
    if discarded_char == "赖":
        return False
    # 检查手中是否有该字面的坎牌
    count = sum(1 for c in hand_cards if c.char == discarded_char)
    # 检查暗牌区是否已有该字面的坎/扎/穿
    for meld in hidden_melds:
        if meld.char == discarded_char and meld.meld_type in (
            MeldType.TRIPLET, MeldType.ZHA, MeldType.CHUAN
        ):
            count += len(meld.cards)
    return count >= 3


def can_fan_from_discard(hidden_melds: list[Meld],
                         discarded_char: str) -> bool:
    """
    判断泛牌情形一：扎牌+旁家打出相同字面。
    """
    if discarded_char == "赖":
        return False
    for meld in hidden_melds:
        if (meld.char == discarded_char and
                meld.meld_type in (MeldType.ZHA, MeldType.CHUAN)):
            return True
    return False


def can_fan_from_hand(hand_cards: list[Card], open_melds: list[Meld]) -> bool:
    """
    判断泛牌情形二：招牌+手中有相同字面。
    """
    for meld in open_melds:
        if meld.meld_type == MeldType.ZHAO:
            zhao_char = meld.char
            if zhao_char in ("三", "五", "七"):
                # 检查手中是否还有该字面
                has_extra = False
                for c in hand_cards:
                    if c.char == zhao_char:
                        # 确保不是已用于招牌的牌
                        if c.id not in [mc.id for mc in meld.cards]:
                            has_extra = True
                            break
                if has_extra:
                    return True
    return False


def get_zha_opportunities(hand_cards: list[Card],
                          hidden_melds: list[Meld]) -> list[str]:
    """获取当前可以执行扎牌的字面列表"""
    counter = _get_char_counter(hand_cards)
    opportunities = []

    for char, count in counter.items():
        # 检查已有坎牌
        total = count
        for meld in hidden_melds:
            if meld.char == char and meld.meld_type == MeldType.TRIPLET:
                total += len(meld.cards)

        if total >= 4:
            # 有坎牌且手中有第4张，可以扎牌
            # 检查是否已有扎/穿
            has_zha_or_chuan = any(
                m.char == char and m.meld_type in (MeldType.ZHA, MeldType.CHUAN)
                for m in hidden_melds
            )
            if not has_zha_or_chuan:
                opportunities.append(char)

    return opportunities


def get_chuan_opportunities(hand_cards: list[Card],
                            hidden_melds: list[Meld]) -> list[str]:
    """获取当前可以执行穿牌的字面列表"""
    counter = _get_char_counter(hand_cards)
    opportunities = []

    for char, count in counter.items():
        total = count
        for meld in hidden_melds:
            if meld.char == char and meld.meld_type == MeldType.ZHA:
                total += len(meld.cards)

        if total >= 5:
            has_chuan = any(
                m.char == char and m.meld_type == MeldType.CHUAN
                for m in hidden_melds
            )
            if not has_chuan:
                opportunities.append(char)

    return opportunities


def get_swap_zha_opportunities(hand_cards: list[Card],
                               hidden_melds: list[Meld]) -> list[dict]:
    """
    获取换扎机会。
    返回: [{"old_char": str, "new_char": str}, ...]
    """
    counter = _get_char_counter(hand_cards)
    opportunities = []

    # 找出当前有扎/穿的牌
    existing_zha = {}
    for meld in hidden_melds:
        if meld.meld_type in (MeldType.ZHA, MeldType.CHUAN):
            existing_zha[meld.char] = meld

    if not existing_zha:
        return opportunities

    # 找出可以形成新扎牌的字面
    for char, count in counter.items():
        if count >= 4 and char not in existing_zha:
            for old_char, old_meld in existing_zha.items():
                opportunities.append({
                    "old_char": old_char,
                    "new_char": char,
                })

    return opportunities


def check_hu(cards: list[Card]) -> dict:
    """
    检查是否可以胡牌。
    传入的是当前手牌（含刚摸到/碰到的牌）。
    """
    return check_ting(cards)


# ============================================================
# 胡牌时加入新牌后的完整检测
# ============================================================

def check_hu_with_card(hand_cards: list[Card], new_card: Card) -> dict:
    """
    检查加入新牌后是否可以胡牌。
    用于自摸(摸牌后)和捉统(旁家出牌后)的判定。
    """
    all_cards = hand_cards + [new_card]
    return check_hu(all_cards)
