"""
花牌游戏 - AI策略模块
实现不同等级的AI玩家策略。
"""

import random
from core.card import Card
from core.player import Player
from core.analyzer import SEQUENCE_SET, check_ting


class AIPlayer:
    """AI玩家基类"""

    def __init__(self, player: Player, level: int = 1):
        self.player = player
        self.level = level
        self.memory: dict = {}  # 记牌信息（Lv4+）

    def choose_discard(self, game_state: dict) -> Card:
        """选择出哪张牌"""
        if self.level <= 1:
            return self._random_discard()
        elif self.level <= 2:
            return self._basic_discard()
        elif self.level <= 3:
            return self._intermediate_discard()
        else:
            return self._advanced_discard()

    def should_zha(self, char: str, game_state: dict) -> bool:
        """是否执行扎牌"""
        if self.level <= 2:
            return random.random() < 0.5
        return random.random() < 0.7

    def should_chuan(self, char: str, game_state: dict) -> bool:
        """是否执行穿牌"""
        if self.level <= 2:
            return random.random() < 0.6
        return random.random() < 0.8

    def should_swap_zha(self, old_char: str, new_char: str,
                        game_state: dict) -> bool:
        """是否换扎"""
        if self.level <= 1:
            return False
        return random.random() < 0.4

    def should_hu(self, score: int, game_state: dict) -> bool:
        """是否胡牌"""
        return score >= 17  # 满足条件就胡

    # ============================================================
    # Lv1: 随机出牌
    # ============================================================

    def _random_discard(self) -> Card:
        """随机出牌"""
        return random.choice(self.player.hand_cards)

    # ============================================================
    # Lv2: 基础规则出牌
    # ============================================================

    def _basic_discard(self) -> Card:
        """基于规则：优先保留顺子/刻子潜力牌"""
        cards = self.player.hand_cards
        scored = []
        for card in cards:
            score = self._eval_card_basic(card)
            scored.append((card, score))

        scored.sort(key=lambda x: x[1])
        return scored[0][0]

    def _eval_card_basic(self, card: Card) -> float:
        """基础牌评估：分越低越应该出"""
        score = 0
        hand_chars = [c.char for c in self.player.hand_cards if c.id != card.id]

        # 能组成顺子
        for seq in SEQUENCE_SET:
            if card.char in seq:
                needed = [c for c in seq if c != card.char]
                if all(n in hand_chars for n in needed):
                    score -= 10

        # 有相同字面
        same = hand_chars.count(card.char)
        if same >= 2:
            score -= 8
        elif same == 1:
            score -= 3

        # 赖子和红精优先保留
        if card.is_wild:
            score -= 20
        if card.is_jing:
            score -= 6

        return score

    # ============================================================
    # Lv3: 中级策略
    # ============================================================

    def _intermediate_discard(self) -> Card:
        """中级：综合考虑听牌距离和胡数"""
        return self._basic_discard()  # 复用基础策略

    # ============================================================
    # Lv4: 高级策略
    # ============================================================

    def _advanced_discard(self) -> Card:
        """高级：记牌+推理"""
        return self._basic_discard()  # 复用基础策略

    # ============================================================
    # 记牌
    # ============================================================

    def memorize_discard(self, player_id: int, card: Card):
        """记忆出牌"""
        if self.level < 4:
            return
        key = card.char
        if key not in self.memory:
            self.memory[key] = {"total": 0, "discarded": 0, "flower": 0}
        self.memory[key]["total"] += 1
        self.memory[key]["discarded"] += 1
        if card.is_flower:
            self.memory[key]["flower"] += 1

    def get_char_remaining(self, char: str) -> int:
        """获取某字面剩余数量"""
        info = self.memory.get(char, {"total": 5, "discarded": 0})
        if char in ("乙", "三", "五", "七", "九"):
            return 5 - info["discarded"]
        elif char == "赖":
            return 2 - info["discarded"]
        return 5 - info["discarded"]

    def reset_memory(self):
        """重置记牌"""
        self.memory = {}
