"""
core/actions.py — 操作判定器
============================
对牌/招牌/扎牌/穿牌/吃牌/泛牌的合法性判定和优先级排序。

花牌操作优先级（从低到高）：
  PASS(0) < CHOW(1) < PEN(2) < ZHAO(3) < CHUAN(4) < ZHA(5) < FAN(6) < HU(10)

3人游戏规则要点：
- 对牌(碰)：任何玩家可对任何其他玩家打出的牌碰牌
- 招牌(杠上)：手中已有坎(3张)，他人打出同字面第4张 → 明杠，取余牌池顶部补牌
- 扎牌(暗杠)：手中持有同字面4张 → 暗杠，取余牌池底部补牌
- 穿牌(泛牌升级)：已有扎牌(4张暗杠)，他人打出同字面第5张 → 明杠升级，取余牌池底部补牌
- 泛牌(5张)：手中持有同字面5张 → 泛牌
- 吃牌(顺子)：只能吃上家(前一位出牌者)的牌组成顺子

反向扎牌阶段：
  上家(2) → 下家(1) → 庄家(0) 依次选择是否扎牌，扎后从余牌池底部补牌
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

from .card import Card
from .melds import (
    ALL_SEQUENCES, CHAR_JING_CATEGORY, JING_CHARS,
    RED_JING_CHARS, BLACK_JING_CHARS, WILD_CHAR, WILD_USABLE_CHARS,
    MeldType,
)


class ActionPriority(IntEnum):
    """操作优先级（数值越大优先级越高）"""
    PASS   = 0    # 过
    CHOW   = 1    # 吃牌（顺子，仅上家）
    PEN    = 2    # 对牌（碰牌）
    ZHAO   = 3    # 招牌（明杠）
    CHUAN  = 4    # 穿牌（5张明杠升级）
    ZHA    = 5    # 扎牌（暗杠，4张）
    FAN    = 6    # 泛牌（5张）
    HU     = 10   # 胡牌


@dataclass
class PlayerAction:
    """玩家可执行操作

    Attributes:
        action_type: 操作类型
        cards: 涉及的牌列表
        source_player: 发起操作的玩家索引
        target_player: 目标玩家索引（被碰/被胡的出牌者，-1表示无目标）
        description: 操作描述
        resulting_meld_type: 操作完成后的牌型
    """
    action_type: ActionPriority
    cards: List[Card]
    source_player: int = -1
    target_player: int = -1
    description: str = ""
    resulting_meld_type: Optional[MeldType] = None

    def __post_init__(self):
        if not self.description:
            names = {
                ActionPriority.PASS: "过", ActionPriority.CHOW: "吃",
                ActionPriority.PEN: "对", ActionPriority.ZHAO: "招",
                ActionPriority.CHUAN: "穿", ActionPriority.ZHA: "扎",
                ActionPriority.FAN: "泛", ActionPriority.HU: "胡",
            }
            card_str = ",".join(str(c) for c in self.cards)
            self.description = f"{names.get(self.action_type, '?')} {card_str}"


class ActionValidator:
    """操作合法性判定器

    负责检查各类操作的合法性，并在有多个操作可选时按优先级排序。
    """

    def __init__(self):
        self._char_cards_cache: Dict[str, List[Card]] = {}

    @staticmethod
    def _count_char(hand: List[Card], char: str) -> int:
        """统计手牌中指定字面的数量"""
        return sum(1 for c in hand if c.char == char)

    @staticmethod
    def _get_char_cards(hand: List[Card], char: str, count: int) -> List[Card]:
        """获取手牌中指定字面的前N张牌"""
        result = []
        for c in hand:
            if c.char == char and len(result) < count:
                result.append(c)
        return result

    # ================================================================
    # 对牌（碰牌）
    # ================================================================

    def check_pen(self, hand: List[Card], played_card: Card,
                  player_index: int, from_player: int) -> Optional[PlayerAction]:
        """检查对牌（碰牌）

        手中有2张与出牌相同字面的牌即可对牌。
        对牌后组成3张明牌。
        """
        if not played_card:
            return None

        count = self._count_char(hand, played_card.char)
        if count >= 2:
            pair_cards = self._get_char_cards(hand, played_card.char, 2)
            if pair_cards:
                return PlayerAction(
                    action_type=ActionPriority.PEN,
                    cards=pair_cards + [played_card],
                    source_player=player_index,
                    target_player=from_player,
                    resulting_meld_type=MeldType.PEN,
                )
        return None

    # ================================================================
    # 招牌（杠上 / 明杠）
    # ================================================================

    def check_zhao(self, hand: List[Card], played_card: Card,
                   player_index: int, from_player: int) -> Optional[PlayerAction]:
        """检查招牌（明杠）

        手中已有坎(3张)，他人打出同字面第4张 → 招牌。
        招牌后取余牌池顶部补一张。
        """
        if not played_card:
            return None

        count = self._count_char(hand, played_card.char)
        if count >= 3:
            kan_cards = self._get_char_cards(hand, played_card.char, 3)
            if kan_cards:
                return PlayerAction(
                    action_type=ActionPriority.ZHAO,
                    cards=kan_cards + [played_card],
                    source_player=player_index,
                    target_player=from_player,
                    resulting_meld_type=MeldType.ZHAO,
                )
        return None

    # ================================================================
    # 穿牌（5张明杠升级）
    # ================================================================

    def check_chuan(self, hand: List[Card], played_card: Card,
                    exposed_melds: List, player_index: int,
                    from_player: int) -> Optional[PlayerAction]:
        """检查穿牌

        已有扎牌(暗杠4张)在场上，他人打出同字面第5张 → 穿牌。
        穿牌后取余牌池底部补一张。
        """
        if not played_card:
            return None

        for meld in exposed_melds:
            if meld.meld_type == MeldType.ZHA and meld.cards[0].char == played_card.char:
                return PlayerAction(
                    action_type=ActionPriority.CHUAN,
                    cards=list(meld.cards) + [played_card],
                    source_player=player_index,
                    target_player=from_player,
                    resulting_meld_type=MeldType.CHUAN,
                )
        return None

    # ================================================================
    # 扎牌（暗杠，4张）
    # ================================================================

    def check_zha(self, hand: List[Card], player_index: int = -1) -> List[PlayerAction]:
        """检查扎牌（暗杠）

        手中持有同字面4张即可扎牌。
        扎牌后取余牌池底部补一张。
        返回所有可扎的字面（一个玩家可能同时有多个字面可扎）。
        """
        actions: List[PlayerAction] = []
        char_counts: Dict[str, List[Card]] = {}
        for c in hand:
            char_counts.setdefault(c.char, []).append(c)

        for char_str, cards in char_counts.items():
            if len(cards) >= 4:
                actions.append(PlayerAction(
                    action_type=ActionPriority.ZHA,
                    cards=cards[:4],
                    source_player=player_index,
                    resulting_meld_type=MeldType.ZHA,
                ))
        return actions

    # ================================================================
    # 泛牌（5张）
    # ================================================================

    def check_fan(self, hand: List[Card], player_index: int = -1) -> List[PlayerAction]:
        """检查泛牌

        手中持有同字面5张即可泛牌。
        泛牌分两种情形：
        - 情形一：已有扎牌(4张) + 他人打出第5张 → 从余牌池顶部取牌
        - 情形二：手中5张直接泛牌
        """
        actions: List[PlayerAction] = []
        char_counts: Dict[str, List[Card]] = {}
        for c in hand:
            char_counts.setdefault(c.char, []).append(c)

        for char_str, cards in char_counts.items():
            if len(cards) >= 5:
                actions.append(PlayerAction(
                    action_type=ActionPriority.FAN,
                    cards=cards[:5],
                    source_player=player_index,
                    resulting_meld_type=MeldType.FAN,
                ))
        return actions

    # ================================================================
    # 吃牌（顺子）
    # ================================================================

    def check_chow(self, hand: List[Card], played_card: Card,
                   player_index: int, from_player: int) -> List[PlayerAction]:
        """检查吃牌（顺子）

        仅能吃上家的牌。
        组成14种顺子之一。
        """
        actions: List[PlayerAction] = []

        if not played_card:
            return actions

        for seq in ALL_SEQUENCES:
            if played_card.char not in seq:
                continue

            needed = [ch for ch in seq if ch != played_card.char]
            available: List[Card] = []
            temp_hand = list(hand)

            for ch in needed:
                found = None
                for c in temp_hand:
                    if c.char == ch:
                        found = c
                        break
                if found is None:
                    break
                available.append(found)
                temp_hand.remove(found)

            if len(available) == len(needed):
                actions.append(PlayerAction(
                    action_type=ActionPriority.CHOW,
                    cards=available + [played_card],
                    source_player=player_index,
                    target_player=from_player,
                    resulting_meld_type=MeldType.SEQUENCE,
                ))

        return actions

    # ================================================================
    # 综合判定
    # ================================================================

    def get_available_actions(
        self,
        hand: List[Card],
        player_index: int,
        played_card: Optional[Card] = None,
        from_player: int = -1,
        exposed_melds: Optional[List] = None,
        check_self_draw: bool = False,
        is_previous_player: bool = False,
    ) -> List[PlayerAction]:
        """获取玩家所有可执行操作

        Args:
            hand: 当前手牌
            player_index: 当前玩家索引
            played_card: 被打出的牌（None表示自摸状态）
            from_player: 出牌的玩家索引
            exposed_melds: 已暴露的牌型（场上明牌/暗牌）
            check_self_draw: 是否检查自摸操作（扎/泛）
            is_previous_player: 当前玩家是否为出牌者的上家（影响吃牌权限）

        Returns:
            按优先级排序的可执行操作列表
        """
        actions: List[PlayerAction] = []
        exposed_melds = exposed_melds or []

        # --- 自摸操作 ---
        if check_self_draw or played_card is None:
            actions.extend(self.check_zha(hand, player_index))
            actions.extend(self.check_fan(hand, player_index))

        # --- 他人出牌后的操作 ---
        if played_card is not None:
            # 穿牌（优先级高于招牌）
            chuan = self.check_chuan(
                hand, played_card, exposed_melds, player_index, from_player,
            )
            if chuan:
                actions.extend(chuan)

            # 招牌（优先级高于对牌）
            zhao = self.check_zhao(hand, played_card, player_index, from_player)
            if zhao:
                actions.append(zhao)

            # 对牌
            pen = self.check_pen(hand, played_card, player_index, from_player)
            if pen:
                actions.append(pen)

            # 吃牌（仅上家可吃）
            if is_previous_player:
                chows = self.check_chow(hand, played_card, player_index, from_player)
                actions.extend(chows)

        # 按优先级降序排列
        actions.sort(key=lambda a: a.action_type, reverse=True)
        return actions

    def resolve_conflict(
        self,
        actions_by_player: Dict[int, List[PlayerAction]],
    ) -> List[PlayerAction]:
        """解决多玩家操作冲突

        规则：
        1. 胡牌优先级最高，任何其他操作都被胡牌压过
        2. 同优先级操作按座位顺序：庄家(0) → 下家(1) → 上家(2)

        Args:
            actions_by_player: {玩家索引: 可执行操作列表}

        Returns:
            最终胜出的操作列表（通常只有一个）
        """
        all_actions: List[PlayerAction] = []
        for player_idx, player_actions in actions_by_player.items():
            for action in player_actions:
                if action.action_type != ActionPriority.PASS:
                    all_actions.append(action)

        if not all_actions:
            return []

        # 找出最高优先级
        max_priority = max(a.action_type for a in all_actions)

        # 过滤出最高优先级的操作
        top_actions = [a for a in all_actions if a.action_type == max_priority]

        # 如果只有一个玩家有最高优先级操作，直接返回
        player_set = set(a.source_player for a in top_actions)
        if len(player_set) == 1:
            return top_actions

        # 多个玩家同优先级时，按座位顺序优先（庄家 > 下家 > 上家）
        top_actions.sort(key=lambda a: a.source_player)
        winner_idx = top_actions[0].source_player
        return [a for a in top_actions if a.source_player == winner_idx]
