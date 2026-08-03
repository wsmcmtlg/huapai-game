"""
ai/base.py — AI 玩家基类
========================
定义 AI 决策接口和公共工具方法。
所有 AI 策略类继承此基类，实现具体决策逻辑。

AI 需要做出以下决策：
1. 出牌决策：手中哪张牌打出
2. 响应决策：对他人出牌的响应（胡/招/对/穿/吃/过）
3. 自摸决策：摸牌后是否胡/扎/泛
4. 扎牌决策：反向扎牌阶段是否扎牌
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import sys
import os

# 确保能导入 core 包
_phase1_path = os.path.join(os.path.dirname(__file__), "..", "Phase 1 规则引擎")
if os.path.exists(_phase1_path) and _phase1_path not in sys.path:
    sys.path.insert(0, os.path.abspath(_phase1_path))

from core.card import Card, Deck
from core.melds import (
    ALL_SEQUENCES, CHAR_COLOR_MAP, CHAR_IS_JING, CHAR_JING_CATEGORY,
    JING_CHARS, RED_JING_CHARS, BLACK_JING_CHARS, WILD_CHAR, WILD_USABLE_CHARS,
    MeldType, RED_SEQUENCES,
)
from core.actions import ActionValidator, PlayerAction, ActionPriority
from core.analyzer import HandAnalyzer
from core.scoring import ScoreCalculator, Meld
from core.player import Player
from core.engine import GameEngine


class AIBase(ABC):
    """AI 玩家基类

    定义 AI 与 GameEngine 交互的标准接口。
    子类只需实现三个核心决策方法即可。

    Attributes:
        player_index: AI 控制的玩家索引
        engine: 游戏引擎引用
        player: 当前玩家对象引用（每局更新）
        validator: 操作判定器
        analyzer: 手牌分析器
        calculator: 胡数计算器
    """

    def __init__(
        self,
        player_index: int,
        engine: GameEngine,
        seed: Optional[int] = None,
    ):
        """初始化 AI

        Args:
            player_index: AI 控制的玩家索引(0/1/2)
            engine: 游戏引擎实例
            seed: 随机种子（None表示不固定）
        """
        self.player_index = player_index
        self.engine = engine
        self.validator = ActionValidator()
        self.analyzer = HandAnalyzer()
        self.calculator = ScoreCalculator()
        self.player: Optional[Player] = None
        self._rng = random.Random(seed)

    # ================================================================
    # 引擎交互 — 每局开始时刷新引用
    # ================================================================

    def refresh_player(self) -> None:
        """刷新玩家引用（每局开始时调用）"""
        if self.engine and self.player_index < len(self.engine.players):
            self.player = self.engine.players[self.player_index]

    @property
    def hand(self) -> List[Card]:
        """当前手牌"""
        return self.player.hand if self.player else []

    # ================================================================
    # 抽象决策接口 — 子类必须实现
    # ================================================================

    @abstractmethod
    def decide_discard(self) -> Optional[Card]:
        """出牌决策

        从手牌中选择一张打出。如果手牌为空返回 None。

        Returns:
            要打出的牌，None 表示无法出牌
        """
        ...

    @abstractmethod
    def decide_response(
        self,
        played_card: Card,
        from_player: int,
        available_actions: List[PlayerAction],
    ) -> Optional[PlayerAction]:
        """响应决策

        对他人出牌做出响应。

        Args:
            played_card: 被打出的牌
            from_player: 出牌的玩家索引
            available_actions: 可执行操作列表（已按优先级排序）

        Returns:
            选择的操作，None 表示过
        """
        ...

    @abstractmethod
    def decide_self_action(
        self,
        available_actions: List[PlayerAction],
    ) -> Optional[PlayerAction]:
        """自摸决策

        摸牌后决定是否胡/扎/泛/穿，还是继续出牌。

        Args:
            available_actions: 可执行操作列表（已按优先级排序）

        Returns:
            选择的操作，None 表示不出牌（继续打牌）
        """
        ...

    def decide_zha(self, available_actions: List[PlayerAction]) -> List[PlayerAction]:
        """反向扎牌决策

        发牌后决定是否扎牌（暗杠）。
        默认实现：所有可扎的全扎。

        Args:
            available_actions: 可扎牌的操作列表

        Returns:
            选择执行的扎牌操作列表
        """
        return [a for a in available_actions
                if a.action_type == ActionPriority.ZHA]

    # ================================================================
    # 公共工具方法 — 子类可直接使用
    # ================================================================

    def get_hand_char_counts(self) -> Dict[str, int]:
        """获取手牌字面计数"""
        return dict(Counter(c.char for c in self.hand))

    def get_char_value_score(self, char: str) -> float:
        """评估单张牌的保留价值（越高越应保留）

        评估维度：
        - 精牌价值高（尤其是主精）
        - 花精 > 皮精 > 普通牌
        - 赖子价值高
        - 散牌（不成对/坎/顺）价值低
        - 已出过的牌价值降低

        Args:
            char: 字面名称

        Returns:
            保留价值分数（0-10）
        """
        score = 0.0
        counts = self.get_hand_char_counts()
        char_count = counts.get(char, 0)

        # ---- 精牌加成 ----
        if char in JING_CHARS:
            score += 3.0
            # 主精额外加分
            if self.player and self.player.is_main_jin(char):
                score += 2.0

            # 红精比黑精更优
            if char in RED_JING_CHARS:
                score += 1.0

        # ---- 赖子 ----
        if char == WILD_CHAR:
            score += 4.0  # 赖子非常灵活，优先保留

        # ---- 成型加成 ----
        if char_count >= 4:
            score += 5.0   # 可以扎牌
        elif char_count == 3:
            score += 4.0   # 可以做坎或等待招牌
        elif char_count == 2:
            score += 2.5   # 对子
        elif char_count == 1:
            score += 0.5   # 单张

        # ---- 顺子潜力 ----
        seq_potential = self._count_sequence_potential(char, counts)
        score += seq_potential * 1.5

        # ---- 已出牌减分 ----
        discarded_count = self._count_discarded(char)
        score -= discarded_count * 0.5

        return max(0, score)

    def _count_sequence_potential(
        self, char: str, counts: Dict[str, int]
    ) -> int:
        """计算字面的顺子潜力（有多少种顺子可以参与）"""
        potential = 0
        for seq in ALL_SEQUENCES:
            if char not in seq:
                continue
            # 检查顺子中其他字面是否在手牌中
            needed = [ch for ch in seq if ch != char]
            available = sum(1 for ch in needed if counts.get(ch, 0) > 0)
            if available >= 1:
                potential += 1
        return potential

    def _count_discarded(self, char: str) -> int:
        """统计场上已打出的指定字面的数量"""
        if not self.engine:
            return 0
        return sum(1 for c in self.engine.discarded if c.char == char)

    def sort_hand_by_value(self) -> List[Tuple[float, Card]]:
        """按牌价值从低到高排序手牌（用于出牌选择）

        Returns:
            [(价值分数, 牌对象)] 按价值升序
        """
        scored = [(self.get_char_value_score(c.char), c) for c in self.hand]
        scored.sort(key=lambda x: (x[0], x[1].id))
        return scored

    def estimate_hand_hu(self) -> int:
        """估算当前手牌（含场上牌型）的总胡数

        Returns:
            估算胡数，分析失败返回0
        """
        if not self.player or not self.analyzer:
            return 0

        all_cards = list(self.player.hand)
        for meld in self.player.melds:
            all_cards.extend(meld.cards)

        result = self.analyzer.analyze_hand(all_cards)
        if result and result.is_win:
            return result.total_hu
        return 0

    def is_close_to_win(self, threshold: int = 12) -> bool:
        """判断是否接近胡牌（胡数 >= threshold）

        Args:
            threshold: 胡数阈值，默认12

        Returns:
            是否接近胡牌
        """
        return self.estimate_hand_hu() >= threshold

    def get_ting_chars(self) -> Set[str]:
        """获取当前听牌的字面集合

        Returns:
            听牌字面集合
        """
        if not self.player or not self.analyzer:
            return set()

        all_cards = list(self.player.hand)
        for meld in self.player.melds:
            all_cards.extend(meld.cards)

        ting = self.analyzer.find_ting_cards(all_cards)
        return set(ting)

    def choose_random_card(self) -> Optional[Card]:
        """随机选一张手牌（备用策略）"""
        if not self.hand:
            return None
        return self._rng.choice(self.hand)

    def log_decision(self, decision_type: str, detail: str) -> None:
        """记录决策日志（可被子类覆盖以实现详细日志）

        Args:
            decision_type: 决策类型（discard/response/self_action/zha）
            detail: 决策详情
        """
        pass  # 默认不输出，子类可覆盖

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"{name}(player={self.player_index})"
