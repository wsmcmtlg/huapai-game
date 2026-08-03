"""
花牌游戏 - 玩家模块
管理玩家手牌、明牌、暗牌、弃牌等状态。
"""

from .card import Card, sort_cards
from .melds import MeldType, FanType, Meld
from .analyzer import (
    can_pen, can_zhao, can_fan_from_discard, can_fan_from_hand,
    get_zha_opportunities, get_chuan_opportunities,
    get_swap_zha_opportunities, check_hu_with_card, check_ting
)


class Player:
    """玩家"""

    def __init__(self, player_id: int, name: str = "", is_ai: bool = False):
        self.id = player_id
        self.name = name or f"玩家{player_id}"
        self.is_ai = is_ai
        self.seat_index: int = -1  # 0=庄, 1=下家, 2=上家
        self.is_dealer: bool = False

        # 牌区
        self.hand_cards: list[Card] = []      # 手牌区（暗牌）
        self.open_melds: list[Meld] = []      # 明牌区（对/招/泛）
        self.hidden_melds: list[Meld] = []    # 暗牌组合（坎/扎/穿）
        self.discard_pile: list[Card] = []    # 弃牌区

        # 状态
        self.is_active: bool = False          # 是否拥有操作权
        self.hu_eligible: bool = True         # 是否有胡牌资格
        self.action_timer: int = 0            # 操作剩余秒数

    # ---------- 牌数查询 ----------

    @property
    def hand_count(self) -> int:
        return len(self.hand_cards)

    @property
    def total_card_count(self) -> int:
        """手中所有牌的数量（含暗牌组合）"""
        total = len(self.hand_cards)
        total += sum(len(m.cards) for m in self.hidden_melds)
        total += sum(len(m.cards) for m in self.open_melds)
        return total

    @property
    def hidden_meld_count(self) -> int:
        return len(self.hidden_melds)

    @property
    def open_meld_count(self) -> int:
        return len(self.open_melds)

    # ---------- 发牌/收牌/出牌 ----------

    def receive_cards(self, cards: list[Card]):
        """收牌（发牌时使用）"""
        self.hand_cards.extend(cards)
        self.hand_cards = sort_cards(self.hand_cards)

    def draw_card(self, card: Card):
        """摸牌"""
        self.hand_cards.append(card)
        self.hand_cards = sort_cards(self.hand_cards)

    def remove_card(self, card: Card) -> Card:
        """从手牌中移除一张牌"""
        for i, c in enumerate(self.hand_cards):
            if c.id == card.id:
                return self.hand_cards.pop(i)
        raise ValueError(f"Card {card} not found in hand")

    def discard(self, card_id: int) -> Card:
        """出牌"""
        for i, c in enumerate(self.hand_cards):
            if c.id == card_id:
                card = self.hand_cards.pop(i)
                self.discard_pile.append(card)
                return card
        raise ValueError(f"Card id {card_id} not found in hand")

    # ---------- 对牌（碰牌） ----------

    def execute_pen(self, discarded_card: Card) -> Meld:
        """
        执行对牌（碰牌）。
        从手牌中取2张相同字面的牌 + 旁家打出的牌组成刻子。
        """
        target_char = discarded_card.char
        pen_cards = [discarded_card]
        taken = 0
        new_hand = []
        for c in self.hand_cards:
            if taken < 2 and c.char == target_char:
                pen_cards.append(c)
                taken += 1
            else:
                new_hand.append(c)
        self.hand_cards = new_hand
        meld = Meld(MeldType.PEN, target_char, pen_cards, is_open=True)
        self.open_melds.append(meld)
        return meld

    # ---------- 招牌 ----------

    def execute_zhao(self, discarded_card: Card) -> Meld:
        """执行招牌。"""
        target_char = discarded_card.char
        zhao_cards = [discarded_card]
        # 从手牌或坎牌中取3张组成4张
        taken = 0

        # 先从坎牌中取
        new_hidden = []
        for meld in self.hidden_melds:
            if taken < 3 and meld.char == target_char and meld.meld_type == MeldType.TRIPLET:
                for c in meld.cards:
                    if taken < 3:
                        zhao_cards.append(c)
                        taken += 1
            else:
                new_hidden.append(meld)
        self.hidden_melds = new_hidden

        # 如果坎牌不够3张，从手牌中补
        if taken < 3:
            new_hand = []
            for c in self.hand_cards:
                if taken < 3 and c.char == target_char:
                    zhao_cards.append(c)
                    taken += 1
                else:
                    new_hand.append(c)
            self.hand_cards = new_hand

        meld = Meld(MeldType.ZHAO, target_char, zhao_cards, is_open=True)
        self.open_melds.append(meld)
        return meld

    # ---------- 扎牌 ----------

    def execute_zha(self, char: str) -> Meld | None:
        """
        执行扎牌。坎牌 + 手中第4张相同字面。
        """
        # 找坎牌
        kan_meld = None
        kan_idx = -1
        for i, m in enumerate(self.hidden_melds):
            if m.char == char and m.meld_type == MeldType.TRIPLET:
                kan_meld = m
                kan_idx = i
                break

        if kan_meld is None:
            return None

        # 从手牌中取一张
        extra_card = None
        new_hand = []
        for c in self.hand_cards:
            if extra_card is None and c.char == char:
                extra_card = c
            else:
                new_hand.append(c)
        self.hand_cards = new_hand

        if extra_card is None:
            return None

        # 替换坎牌为扎牌
        zha_cards = kan_meld.cards + [extra_card]
        self.hidden_melds.pop(kan_idx)
        meld = Meld(MeldType.ZHA, char, zha_cards)
        self.hidden_melds.append(meld)
        return meld

    # ---------- 穿牌 ----------

    def execute_chuan(self, char: str) -> Meld | None:
        """执行穿牌。扎牌 + 手中第5张相同字面。"""
        zha_meld = None
        zha_idx = -1
        for i, m in enumerate(self.hidden_melds):
            if m.char == char and m.meld_type == MeldType.ZHA:
                zha_meld = m
                zha_idx = i
                break

        if zha_meld is None:
            return None

        extra_card = None
        new_hand = []
        for c in self.hand_cards:
            if extra_card is None and c.char == char:
                extra_card = c
            else:
                new_hand.append(c)
        self.hand_cards = new_hand

        if extra_card is None:
            return None

        chuan_cards = zha_meld.cards + [extra_card]
        self.hidden_melds.pop(zha_idx)
        meld = Meld(MeldType.CHUAN, char, chuan_cards)
        self.hidden_melds.append(meld)
        return meld

    # ---------- 泛牌 ----------

    def execute_fan_type1(self, discarded_card: Card) -> Meld | None:
        """
        执行泛牌情形一：扎牌 + 旁家打出相同字面。
        """
        zha_meld = None
        zha_idx = -1
        for i, m in enumerate(self.hidden_melds):
            if (m.char == discarded_card.char and
                    m.meld_type in (MeldType.ZHA, MeldType.CHUAN)):
                zha_meld = m
                zha_idx = i
                break

        if zha_meld is None:
            return None

        fan_cards = zha_meld.cards + [discarded_card]
        self.hidden_melds.pop(zha_idx)
        meld = Meld(MeldType.FAN, discarded_card.char, fan_cards,
                     is_open=True, fan_type=FanType.FROM_DISCARD)
        self.open_melds.append(meld)
        return meld

    def execute_fan_type2(self) -> Meld | None:
        """
        执行泛牌情形二：招牌 + 手中有相同字面。
        """
        zhao_meld = None
        zhao_idx = -1
        for i, m in enumerate(self.open_melds):
            if m.meld_type == MeldType.ZHAO and m.char in ("三", "五", "七"):
                # 检查手中有无额外牌
                has_extra = False
                for c in self.hand_cards:
                    if c.char == m.char and c.id not in [mc.id for mc in m.cards]:
                        has_extra = True
                        break
                if has_extra:
                    zhao_meld = m
                    zhao_idx = i
                    break

        if zhao_meld is None:
            return None

        extra_card = None
        new_hand = []
        for c in self.hand_cards:
            if extra_card is None and c.char == zhao_meld.char:
                if c.id not in [mc.id for mc in zhao_meld.cards]:
                    extra_card = c
                else:
                    new_hand.append(c)
            else:
                new_hand.append(c)
        self.hand_cards = new_hand

        if extra_card is None:
            return None

        fan_cards = zhao_meld.cards + [extra_card]
        self.open_melds.pop(zhao_idx)
        meld = Meld(MeldType.FAN, zhao_meld.char, fan_cards,
                     is_open=True, fan_type=FanType.FROM_HAND)
        self.open_melds.append(meld)
        return meld

    # ---------- 换扎 ----------

    def execute_swap_zha(self, old_char: str, new_char: str) -> bool:
        """执行换扎。"""
        # 移除旧扎牌
        old_idx = -1
        old_meld = None
        for i, m in enumerate(self.hidden_melds):
            if m.char == old_char and m.meld_type in (MeldType.ZHA, MeldType.CHUAN):
                old_meld = m
                old_idx = i
                break

        if old_meld is None:
            return False

        # 旧扎牌的牌回到手牌
        self.hand_cards.extend(old_meld.cards)
        self.hidden_melds.pop(old_idx)

        # 执行新扎牌
        result = self.execute_zha(new_char)
        if result is None:
            return False
        return True

    # ---------- 可用操作查询 ----------

    def get_valid_actions_on_discard(self, discarded_card: Card) -> list[dict]:
        """
        获取对旁家出牌的可用操作列表。
        按优先级排序: 胡 > 泛 > 招 > 对
        """
        actions = []

        # 胡牌检查（捉统）
        if self.hu_eligible:
            hu_result = check_hu_with_card(self.hand_cards, discarded_card)
            if hu_result["is_ting"]:
                actions.append({
                    "action": "hu",
                    "score": hu_result["best_score"],
                    "zhu_jing": hu_result["zhu_jing"],
                    "priority": 0,
                })

        # 泛牌检查（情形一）
        if can_fan_from_discard(self.hidden_melds, discarded_card.char):
            actions.append({
                "action": "fan",
                "fan_type": "from_discard",
                "priority": 1,
            })

        # 泛牌检查（情形二）
        if can_fan_from_hand(self.hand_cards, self.open_melds):
            actions.append({
                "action": "fan",
                "fan_type": "from_hand",
                "priority": 1,
            })

        # 招牌检查
        if can_zhao(self.hand_cards, self.hidden_melds, discarded_card.char):
            actions.append({
                "action": "zhao",
                "priority": 2,
            })

        # 对牌检查
        if can_pen(self.hand_cards, discarded_card.char):
            actions.append({
                "action": "pen",
                "priority": 3,
            })

        return sorted(actions, key=lambda a: a["priority"])

    def get_valid_actions_on_draw(self) -> list[dict]:
        """
        获取摸牌后的可用操作列表。
        按优先级排序: 胡 > 穿 > 扎 > 换扎 > 出牌
        """
        actions = []

        # 胡牌检查（自摸）
        if self.hu_eligible:
            hu_result = check_ting(self.hand_cards)
            if hu_result["is_ting"]:
                actions.append({
                    "action": "hu",
                    "score": hu_result["best_score"],
                    "zhu_jing": hu_result["zhu_jing"],
                    "priority": 0,
                })

        # 穿牌
        for char in get_chuan_opportunities(self.hand_cards, self.hidden_melds):
            actions.append({"action": "chuan", "char": char, "priority": 1})

        # 扎牌
        for char in get_zha_opportunities(self.hand_cards, self.hidden_melds):
            actions.append({"action": "zha", "char": char, "priority": 2})

        # 换扎
        for opp in get_swap_zha_opportunities(self.hand_cards, self.hidden_melds):
            actions.append({
                "action": "swap_zha",
                "old_char": opp["old_char"],
                "new_char": opp["new_char"],
                "priority": 3,
            })

        # 出牌（始终可用）
        actions.append({"action": "discard", "priority": 4})

        return sorted(actions, key=lambda a: a["priority"])

    # ---------- 获取所有牌（含暗牌组合）用于分析 ----------

    def get_all_cards(self) -> list[Card]:
        """获取所有手牌（含暗牌组合中的牌）"""
        all_cards = self.hand_cards[:]
        for meld in self.hidden_melds:
            all_cards.extend(meld.cards)
        for meld in self.open_melds:
            all_cards.extend(meld.cards)
        return all_cards

    def get_hand_for_analysis(self) -> list[Card]:
        """获取用于胡牌分析的所有牌"""
        return self.get_all_cards()

    # ---------- 序列化 ----------

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "seat_index": self.seat_index,
            "is_dealer": self.is_dealer,
            "is_ai": self.is_ai,
            "hand_count": self.hand_count,
            "hand_cards": [c.to_dict() for c in self.hand_cards],
            "open_melds": [
                {"type": m.meld_type.value, "char": m.char,
                 "card_ids": [c.id for c in m.cards]}
                for m in self.open_melds
            ],
            "hidden_melds": [
                {"type": m.meld_type.value, "char": m.char,
                 "card_ids": [c.id for c in m.cards]}
                for m in self.hidden_melds
            ],
            "discard_count": len(self.discard_pile),
            "is_active": self.is_active,
            "hu_eligible": self.hu_eligible,
        }

    def __repr__(self):
        return (f"Player(id={self.id}, name={self.name}, "
                f"seat={self.seat_index}, dealer={self.is_dealer}, "
                f"hand={self.hand_count})")
