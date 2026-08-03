"""
ai/medium.py — 中级 AI 策略
==========================
具备听牌判断、胡牌追求和基础策略选择的中级AI。

策略特点：
- 出牌：基于听牌判断，优先打不影响听牌的牌；保留精牌组合潜力
- 响应：综合考虑胡数收益和听牌面，不盲目对/吃
- 自摸：评估自摸后手牌结构，合理选择扎牌时机
- 听牌：能计算当前听哪些牌，优先打出不影响听牌的牌
- 胡牌追求：接近胡牌时更保守（不拆关键牌），远离胡牌时更激进

与 SimpleAI 的关键区别：
1. 出牌前计算听牌集合，确保出牌不破坏听牌
2. 对牌/吃牌有选择性（可能选择过牌以保持手牌结构）
3. 精牌组合意识更强（保留三/五/七的成型潜力）
4. 余牌感知（考虑已出牌来评估某张牌的实用性）
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Dict, List, Optional, Set, Tuple

from .base import AIBase

from core.card import Card
from core.melds import (
    ALL_SEQUENCES, CHAR_COLOR_MAP, CHAR_IS_JING, CHAR_JING_CATEGORY,
    JING_CHARS, RED_JING_CHARS, BLACK_JING_CHARS, WILD_CHAR,
    WILD_USABLE_CHARS, MeldType, RED_SEQUENCES,
    NUMBER_SEQUENCES, MIN_HU_SCORE,
)
from core.actions import ActionValidator, PlayerAction, ActionPriority
from core.scoring import ScoreCalculator, Meld


class MediumAI(AIBase):
    """中级 AI 策略

    在 SimpleAI 基础上增加：
    - 听牌感知：出牌前模拟打出后是否能听牌
    - 胡数评估：接近17胡时更积极胡牌，远离时更注重手牌发展
    - 选择性对/吃：不破坏手牌结构的对/吃才执行
    - 余牌感知：已大量出过的牌价值降低
    """

    def decide_discard(self) -> Optional[Card]:
        """出牌决策：高级选牌策略

        步骤：
        1. 计算当前听牌集合
        2. 遍历每张手牌，模拟打出后检查是否仍然听牌
        3. 选一张打出后仍然听牌且价值最低的牌
        4. 如果没有这样的牌，退化为打价值最低的散牌
        """
        if not self.hand:
            return None

        counts = self.get_hand_char_counts()
        current_hu = self.estimate_hand_hu()
        is_close = current_hu >= 10  # 接近胡牌的阈值

        # ---- 策略分支：接近胡牌时保守，远离时发展 ----
        if is_close:
            return self._discard_conservative(counts)
        else:
            return self._discard_developmental(counts)

    def _discard_conservative(self, counts: Dict[str, int]) -> Optional[Card]:
        """保守出牌策略（接近胡牌时）

        优先级：
        1. 打出后仍然听牌的最低价值牌
        2. 非精牌、非赖子的单张
        3. 价值最低的牌
        """
        # 尝试找打出后仍听牌的牌
        safe_discards = self._find_safe_discards()
        if safe_discards:
            scored_safe = [
                (self.get_char_value_score(c.char), c)
                for c in safe_discards
            ]
            scored_safe.sort(key=lambda x: x[0])
            card = scored_safe[0][1]
            self.log_decision("discard", f"[保守]安全出牌(仍听牌): {card}")
            return card

        # 没有安全牌，打单张非精非赖
        scored = self.sort_hand_by_value()
        for score, card in scored:
            if counts[card.char] == 1 and card.char not in JING_CHARS and card.char != WILD_CHAR:
                self.log_decision("discard", f"[保守]打单张散牌: {card}")
                return card

        # 兜底
        card = scored[0][1]
        self.log_decision("discard", f"[保守]兜底出牌: {card}")
        return card

    def _discard_developmental(self, counts: Dict[str, int]) -> Optional[Card]:
        """发展型出牌策略（远离胡牌时）

        优先级：
        1. 打出后能增加听牌面的牌
        2. 已大量出过的字面（获取概率低）
        3. 非精非赖单张散牌
        4. 价值最低的牌
        """
        # 找打出后能增加听牌面的牌
        improved = self._find_improved_discards()
        if improved:
            card = improved[0]
            self.log_decision("discard", f"[发展]增加听牌面: {card}")
            return card

        scored = self.sort_hand_by_value()

        # 打已大量出过的散牌（减少手中废牌）
        for score, card in scored:
            if counts[card.char] == 1:
                discarded = self._count_discarded(card.char)
                total_in_game = 5 if card.char != WILD_CHAR else 2
                remaining = total_in_game - discarded - counts[card.char]
                if remaining <= 1 and card.char not in JING_CHARS:
                    self.log_decision("discard", f"[发展]打绝张/近绝张: {card}")
                    return card

        # 非精非赖单张
        for score, card in scored:
            if counts[card.char] == 1 and card.char not in JING_CHARS and card.char != WILD_CHAR:
                self.log_decision("discard", f"[发展]打散牌: {card}")
                return card

        # 兜底
        card = scored[0][1]
        self.log_decision("discard", f"[发展]兜底: {card}")
        return card

    def _find_safe_discards(self) -> List[Card]:
        """找出打出后仍然听牌的牌

        Returns:
            安全出牌列表
        """
        if not self.player or not self.analyzer:
            return []

        current_ting = self.get_ting_chars()
        if not current_ting:
            return []  # 当前不听牌

        safe = []
        for card in self.hand:
            # 模拟打出这张牌
            test_hand = [c for c in self.hand if c.id != card.id]
            test_cards = list(test_hand)
            for meld in self.player.melds:
                test_cards.extend(meld.cards)

            new_ting = self.analyzer.find_ting_cards(test_cards)
            if set(new_ting) & current_ting:
                # 打出后仍能听原来的牌（至少有交集）
                safe.append(card)
            elif new_ting:
                # 打出后听不同的牌，也算安全
                safe.append(card)

        return safe

    def _find_improved_discards(self) -> List[Card]:
        """找出打出后能增加听牌面的牌

        Returns:
            改善听牌的出牌列表
        """
        if not self.player or not self.analyzer:
            return []

        current_ting = self.get_ting_chars()
        improved = []

        for card in self.hand:
            test_hand = [c for c in self.hand if c.id != card.id]
            test_cards = list(test_hand)
            for meld in self.player.melds:
                test_cards.extend(meld.cards)

            new_ting = set(self.analyzer.find_ting_cards(test_cards))

            if len(new_ting) > len(current_ting):
                improved.append(card)

        return improved

    # ================================================================
    # 响应决策
    # ================================================================

    def decide_response(
        self,
        played_card: Card,
        from_player: int,
        available_actions: List[PlayerAction],
    ) -> Optional[PlayerAction]:
        """响应决策（中级策略）

        策略：
        1. 胡牌：胡数 >= 17 必胡；< 17 时根据听牌情况决定
        2. 穿牌：总是穿（收益最高）
        3. 招牌：评估招牌后是否仍然听牌
        4. 对牌：评估碰牌后是否仍然听牌或增加听牌面
        5. 吃牌：仅当顺子有助于听牌时才吃
        """
        if not available_actions:
            self.log_decision("response", "过")
            return None

        current_hu = self.estimate_hand_hu()

        # 1. 胡牌判断
        for action in available_actions:
            if action.action_type == ActionPriority.HU:
                if current_hu >= MIN_HU_SCORE:
                    self.log_decision("response", f"胡牌！{current_hu}胡 {action.description}")
                    return action
                # 胡数不够时也胡（因为能胡说明分析器认为胡了）
                self.log_decision("response", f"胡牌(判定可胡) {action.description}")
                return action

        # 2. 穿牌（总是穿）
        for action in available_actions:
            if action.action_type == ActionPriority.CHUAN:
                self.log_decision("response", f"穿牌: {action.description}")
                return action

        # 3. 招牌 — 评估后决定
        for action in available_actions:
            if action.action_type == ActionPriority.ZHAO:
                if self._should_zhao(action):
                    self.log_decision("response", f"招牌: {action.description}")
                    return action

        # 4. 对牌 — 评估后决定
        pen_actions = [a for a in available_actions
                       if a.action_type == ActionPriority.PEN]
        if pen_actions:
            # 优先对精牌
            jing_pen = [a for a in pen_actions
                        if a.cards[0].char in JING_CHARS]
            if jing_pen:
                action = jing_pen[0]
                if self._should_pen(action):
                    self.log_decision("response", f"对精牌: {action.description}")
                    return action
            # 普通对牌 — 50%概率对
            if self._rng.random() < 0.5:
                action = pen_actions[0]
                if self._should_pen(action):
                    self.log_decision("response", f"对牌(评估通过): {action.description}")
                    return action

        # 5. 吃牌 — 选择性吃
        chow_actions = [a for a in available_actions
                        if a.action_type == ActionPriority.CHOW]
        if chow_actions:
            # 优先吃含精牌/主精的顺子
            best_chow = None
            best_score = -1
            for action in chow_actions:
                score = sum(
                    3 if c.char in JING_CHARS else (1 if c.is_red else 0)
                    for c in action.cards
                )
                if score > best_score:
                    best_score = score
                    best_chow = action

            if best_chow and self._rng.random() < 0.4:
                self.log_decision("response", f"吃牌(选择性): {best_chow.description}")
                return best_chow

        self.log_decision("response", "过")
        return None

    def _should_zhao(self, action: PlayerAction) -> bool:
        """判断是否应该招牌

        招牌后需要补牌，如果当前手牌结构好则招。
        """
        # 招精牌总是划算
        char = action.cards[0].char
        if char in JING_CHARS:
            return True

        # 手牌较少时更倾向招
        if self.player and self.player.hand_size <= 10:
            return True

        return self._rng.random() < 0.7

    def _should_pen(self, action: PlayerAction) -> bool:
        """判断是否应该对牌

        对牌后需要出牌，考虑是否会破坏手牌结构。
        """
        if not self.player:
            return True

        char = action.cards[0].char
        counts = self.get_hand_char_counts()

        # 如果只有这一对，对牌后减少一张听牌可能，需要谨慎
        if counts.get(char, 0) == 2:
            # 检查对牌后手牌是否仍然有好结构
            remaining = self.player.hand_size - 2  # 移除手中2张
            if remaining <= 5:
                return True  # 手牌少了，碰了减少不确定性

        # 精牌对子总是对
        if char in JING_CHARS:
            return True

        return True

    # ================================================================
    # 自摸决策
    # ================================================================

    def decide_self_action(
        self,
        available_actions: List[PlayerAction],
    ) -> Optional[PlayerAction]:
        """自摸决策

        策略：
        1. 胡牌必胡
        2. 泛牌必泛
        3. 扎牌评估：手牌多时扎，手牌少且接近胡牌时考虑不扎
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

        # 3. 扎牌 — 评估时机
        zha_actions = [a for a in available_actions
                       if a.action_type == ActionPriority.ZHA]
        if zha_actions:
            # 手牌 >= 8 时扎牌（扎后补一张，净减少3张）
            if self.player and self.player.hand_size >= 8:
                action = zha_actions[0]
                self.log_decision("self_action", f"扎牌: {action.description}")
                return action
            # 接近胡牌时不扎（保留手牌灵活性）
            elif self.is_close_to_win(10):
                self.log_decision("self_action", "接近胡牌，不扎牌")
                return None
            else:
                action = zha_actions[0]
                self.log_decision("self_action", f"扎牌(默认): {action.description}")
                return action

        return None

    def decide_zha(self, available_actions: List[PlayerAction]) -> List[PlayerAction]:
        """反向扎牌决策

        策略：
        - 手牌多时扎牌
        - 精牌扎牌优先
        - 普通牌4张时，如果手中牌数>=12才扎
        """
        zha_actions = [a for a in available_actions
                       if a.action_type == ActionPriority.ZHA]

        if not zha_actions:
            return []

        selected = []
        hand_size = self.player.hand_size if self.player else 25

        for action in zha_actions:
            char = action.cards[0].char

            # 精牌扎牌优先
            if char in JING_CHARS:
                selected.append(action)
            elif hand_size >= 14:
                # 手牌够多，可以扎
                selected.append(action)

        if selected:
            self.log_decision("zha", f"扎牌{len(selected)}组(手牌{hand_size}张)")
        else:
            self.log_decision("zha", f"不扎牌(手牌{hand_size}张)")

        return selected
