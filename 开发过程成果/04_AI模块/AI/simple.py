"""
ai/simple.py — 简单 AI 策略
==========================
基于规则启发式的初级策略，行为类似初学者玩家。

策略特点：
- 出牌：打价值最低的牌（优先打散牌，保留对子/坎/顺子潜力牌）
- 响应：胡牌必胡，其余按固定偏好（招牌 > 对牌 > 吃牌）
- 自摸：胡牌必胡，有扎必扎
- 扎牌：有扎必扎
- 不做听牌判断，不做复杂胡数计算
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Set, Tuple

from .base import AIBase

from core.card import Card
from core.melds import (
    MeldType, JING_CHARS, RED_JING_CHARS,
    WILD_CHAR, WILD_USABLE_CHARS, ALL_SEQUENCES,
)
from core.actions import ActionValidator, PlayerAction, ActionPriority
from core.scoring import ScoreCalculator, Meld


class SimpleAI(AIBase):
    """简单 AI 策略（初学者级别）

    决策逻辑简单直接：
    1. 能胡就胡
    2. 能招就招（招牌收益高）
    3. 能对就对（碰牌形成对子）
    4. 能穿就穿（穿牌收益高）
    5. 能吃就吃（吃牌凑顺子）
    6. 出牌打最没用的
    """

    def decide_discard(self) -> Optional[Card]:
        """出牌决策：打价值最低的牌

        策略：
        1. 找出所有单张散牌（不成对/不成顺的孤立牌）
        2. 从散牌中选价值最低的打出
        3. 如果没有散牌，选价值最低的牌打出
        """
        if not self.hand:
            return None

        counts = self.get_hand_char_counts()
        scored = self.sort_hand_by_value()

        # 优先级1：非精牌、非赖子的单张散牌
        single_discards = [
            (score, card) for score, card in scored
            if counts[card.char] == 1
            and card.char not in JING_CHARS
            and card.char != WILD_CHAR
        ]
        if single_discards:
            card = single_discards[0][1]
            self.log_decision("discard", f"打单张散牌: {card}")
            return card

        # 优先级2：赖子单张（赖子在没有三/五/七时可考虑打出）
        wild_discards = [
            (score, card) for score, card in scored
            if card.char == WILD_CHAR and counts.get(WILD_CHAR, 0) <= 1
        ]
        # 检查手中是否有三/五/七可以用赖子替代
        has_357 = any(c in counts for c in WILD_USABLE_CHARS if counts.get(c, 0) > 0)
        if wild_discards and not has_357:
            card = wild_discards[0][1]
            self.log_decision("discard", f"打多余赖子: {card}")
            return card

        # 优先级3：精牌单张
        jing_singles = [
            (score, card) for score, card in scored
            if counts[card.char] == 1 and card.char in JING_CHARS
        ]
        if jing_singles:
            card = jing_singles[0][1]
            self.log_decision("discard", f"打精牌单张: {card}")
            return card

        # 优先级4：对子中选价值最低的拆一张
        pair_discards = [
            (score, card) for score, card in scored
            if counts[card.char] == 2
        ]
        if pair_discards:
            card = pair_discards[0][1]
            self.log_decision("discard", f"拆对子: {card}")
            return card

        # 兜底：打价值最低的
        card = scored[0][1]
        self.log_decision("discard", f"打最低价值牌: {card}")
        return card

    def decide_response(
        self,
        played_card: Card,
        from_player: int,
        available_actions: List[PlayerAction],
    ) -> Optional[PlayerAction]:
        """响应决策

        策略：
        1. 有胡必胡
        2. 招牌（明杠）优先级高，总是招
        3. 穿牌收益高，总是穿
        4. 对牌（碰）总是对
        5. 吃牌：评估顺子价值，有选择地吃
        """
        if not available_actions:
            self.log_decision("response", "过")
            return None

        # 1. 胡牌必胡
        for action in available_actions:
            if action.action_type == ActionPriority.HU:
                self.log_decision("response", f"胡牌！{action.description}")
                return action

        # 2. 穿牌（5张明杠）— 收益很高，总是穿
        for action in available_actions:
            if action.action_type == ActionPriority.CHUAN:
                self.log_decision("response", f"穿牌: {action.description}")
                return action

        # 3. 招牌（明杠）— 总是招
        for action in available_actions:
            if action.action_type == ActionPriority.ZHAO:
                self.log_decision("response", f"招牌: {action.description}")
                return action

        # 4. 对牌（碰牌）— 总是对
        for action in available_actions:
            if action.action_type == ActionPriority.PEN:
                self.log_decision("response", f"对牌: {action.description}")
                return action

        # 5. 吃牌 — 简单判断：如果顺子中有精牌就吃，否则50%概率吃
        chow_actions = [
            a for a in available_actions
            if a.action_type == ActionPriority.CHOW
        ]
        if chow_actions:
            # 优先吃含精牌的顺子
            jing_chows = [
                a for a in chow_actions
                if any(c.char in JING_CHARS or c.char == WILD_CHAR
                       for c in a.cards)
            ]
            if jing_chows:
                action = jing_chows[0]
                self.log_decision("response", f"吃含精牌顺子: {action.description}")
                return action

            # 50% 概率吃普通顺子
            if self._rng.random() < 0.5:
                action = self._rng.choice(chow_actions)
                self.log_decision("response", f"吃牌(随机): {action.description}")
                return action

        self.log_decision("response", "过")
        return None

    def decide_self_action(
        self,
        available_actions: List[PlayerAction],
    ) -> Optional[PlayerAction]:
        """自摸决策

        策略：
        1. 有胡必胡
        2. 有泛就泛（5张全齐）
        3. 有扎就扎（暗杠）
        """
        if not available_actions:
            return None

        # 1. 胡牌
        for action in available_actions:
            if action.action_type == ActionPriority.HU:
                self.log_decision("self_action", f"自摸胡！{action.description}")
                return action

        # 2. 泛牌
        for action in available_actions:
            if action.action_type == ActionPriority.FAN:
                self.log_decision("self_action", f"泛牌: {action.description}")
                return action

        # 3. 扎牌
        for action in available_actions:
            if action.action_type == ActionPriority.ZHA:
                self.log_decision("self_action", f"扎牌: {action.description}")
                return action

        return None

    def decide_zha(self, available_actions: List[PlayerAction]) -> List[PlayerAction]:
        """反向扎牌：有扎必扎"""
        zha_actions = [a for a in available_actions
                       if a.action_type == ActionPriority.ZHA]
        if zha_actions:
            self.log_decision("zha", f"扎牌{len(zha_actions)}组")
        return zha_actions
