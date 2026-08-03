"""
core/player.py — 玩家模块
=========================
定义玩家状态数据结构及手牌管理方法。

3人游戏座位：
  0 = 庄家（东）
  1 = 下家（南）
  2 = 上家（西）

玩家管理：手牌增删、字面计数、牌型组成、精牌设置。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .card import Card
from .melds import MeldType, Direction


@dataclass
class Player:
    """玩家数据结构

    Attributes:
        index: 座位索引（0=庄家, 1=下家, 2=上家）
        name: 玩家名称
        hand: 手牌列表
        melds: 已组成的牌型列表（场上的明牌/暗牌）
        is_dealer: 是否为庄家
        is_active: 是否活跃（未胡牌/未出局）
        last_drawn: 最近摸到的牌
        main_jin_char: 本局主精字面
        vice_jin_char: 本局副精字面
    """
    index: int = 0
    name: str = ""
    hand: List[Card] = field(default_factory=list)
    melds: list = field(default_factory=list)
    is_dealer: bool = False
    is_active: bool = True
    last_drawn: Optional[Card] = None
    main_jin_char: Optional[str] = None
    vice_jin_char: Optional[str] = None
    _hand_counts: Dict[str, int] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self._update_counts()

    def _update_counts(self):
        """更新手牌字面计数缓存"""
        self._hand_counts = dict(Counter(c.char for c in self.hand))

    @property
    def direction(self) -> Direction:
        """座位方向"""
        directions = {0: Direction.EAST, 1: Direction.SOUTH, 2: Direction.WEST}
        return directions.get(self.index, Direction.EAST)

    @property
    def hand_size(self) -> int:
        """当前手牌数"""
        return len(self.hand)

    # ================================================================
    # 手牌管理
    # ================================================================

    def add_card(self, card: Card) -> None:
        """添加一张牌到手牌"""
        self.hand.append(card)
        self._hand_counts[card.char] = self._hand_counts.get(card.char, 0) + 1

    def remove_card(self, card: Card) -> bool:
        """从手牌中移除一张牌（按id匹配）

        Returns:
            是否成功移除
        """
        for i, c in enumerate(self.hand):
            if c.id == card.id:
                self.hand.pop(i)
                self._hand_counts[card.char] -= 1
                if self._hand_counts[card.char] <= 0:
                    del self._hand_counts[card.char]
                return True
        return False

    def remove_cards(self, cards: List[Card]) -> bool:
        """批量移除手牌

        Returns:
            是否全部成功移除
        """
        for card in cards:
            if not self.remove_card(card):
                return False
        return True

    def has_char(self, char: str, count: int = 1) -> bool:
        """检查手牌中是否有足够数量的指定字面"""
        return self._hand_counts.get(char, 0) >= count

    def get_char_count(self, char: str) -> int:
        """获取手牌中指定字面的数量"""
        return self._hand_counts.get(char, 0)

    def get_cards_by_char(self, char: str, count: int = -1) -> List[Card]:
        """获取手牌中指定字面的牌

        Args:
            char: 字面名称
            count: 需要的数量，-1表示全部
        """
        result = [c for c in self.hand if c.char == char]
        if count > 0:
            result = result[:count]
        return result

    def sort_hand(self) -> None:
        """按字面类型和ID排序手牌"""
        self.hand.sort(key=lambda c: (c.char_type.value, c.id))

    # ================================================================
    # 牌型管理
    # ================================================================

    def add_meld(self, meld) -> None:
        """添加一个牌型到场上

        Args:
            meld: scoring.Meld 对象
        """
        # 从手牌中移除组成牌型的牌
        for card in meld.cards:
            self.remove_card(card)
        self.melds.append(meld)

    def get_exposed_melds(self) -> list:
        """获取已暴露的牌型列表（明牌/暗牌均返回）"""
        return list(self.melds)

    def get_open_melds(self) -> list:
        """获取明牌（对牌/招牌/穿牌）"""
        return [m for m in self.melds if m.is_open]

    def get_zha_melds(self) -> list:
        """获取扎牌列表（用于穿牌判定）"""
        from .melds import MeldType
        return [m for m in self.melds if m.meld_type == MeldType.ZHA]

    # ================================================================
    # 精牌设置
    # ================================================================

    def set_jin_pai(self, main_jin_char: Optional[str],
                    vice_jin_char: Optional[str] = None) -> None:
        """设置本局主精/副精"""
        self.main_jin_char = main_jin_char
        self.vice_jin_char = vice_jin_char

    def is_main_jin(self, char: str) -> bool:
        """判断是否为主精字面"""
        return char == self.main_jin_char

    def is_jing_char(self, char: str) -> bool:
        """判断是否为精牌字面"""
        from .melds import JING_CHARS
        return char in JING_CHARS

    # ================================================================
    # 局重置
    # ================================================================

    def reset_for_new_round(self) -> None:
        """重置为新的一局"""
        self.hand.clear()
        self.melds.clear()
        self.last_drawn = None
        self._hand_counts.clear()
        self.main_jin_char = None
        self.vice_jin_char = None
        self.is_active = True

    def set_hand(self, cards: List[Card]) -> None:
        """设置手牌（发牌后使用）"""
        self.hand = list(cards)
        self._update_counts()

    # ================================================================
    # 显示
    # ================================================================

    def hand_summary(self) -> str:
        """手牌摘要字符串"""
        chars = "".join(str(c) for c in self.hand)
        return f"{self.name}: [{chars}] ({len(self.hand)}张)"

    def meld_summary(self) -> str:
        """场上牌型摘要"""
        parts = [str(m) for m in self.melds]
        return f"{self.name} 场上: {', '.join(parts)}" if parts else f"{self.name} 场上: 无"

    def __repr__(self) -> str:
        d = " [庄]" if self.is_dealer else ""
        return (
            f"Player({self.index}, '{self.name}'{d}, "
            f"hand={len(self.hand)}, melds={len(self.melds)})"
        )
