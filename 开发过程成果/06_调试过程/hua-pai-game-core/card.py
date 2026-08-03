"""
花牌游戏 - 牌面定义和牌组管理模块
包含Card类（单张牌）和Deck类（牌组管理）。
"""

import random
from .melds import (
    CharType, Color, JingSubType, JING_CHARS, CHAR_ATTRIBUTES
)


class Card:
    """单张牌"""

    __slots__ = ('id', 'char', 'char_type', 'color', 'is_gold', 'jing_sub_type')

    def __init__(self, id_: int, char: str, char_type: CharType,
                 color: Color, is_gold: bool = False,
                 jing_sub_type: JingSubType = JingSubType.NONE):
        self.id = id_
        self.char = char
        self.char_type = char_type
        self.color = color
        self.is_gold = is_gold
        self.jing_sub_type = jing_sub_type

    # ---------- 属性快捷方法 ----------

    @property
    def is_jing(self) -> bool:
        return self.char_type in (CharType.RED_JING, CharType.BLACK_JING)

    @property
    def is_red(self) -> bool:
        return self.color == Color.RED

    @property
    def is_black(self) -> bool:
        return self.color == Color.BLACK

    @property
    def is_wild(self) -> bool:
        return self.char_type == CharType.WILD

    @property
    def is_flower(self) -> bool:
        """是否为花精（描金精牌）"""
        return self.jing_sub_type == JingSubType.FLOWER

    @property
    def is_skin(self) -> bool:
        """是否为皮精（非描金精牌）"""
        return self.jing_sub_type == JingSubType.SKIN

    # ---------- 可通配判断 ----------

    def can_represent(self, target_char: str) -> bool:
        """判断赖子是否可以通配目标字面"""
        if not self.is_wild:
            return False
        return target_char in ("三", "五", "七")

    def effective_char(self, target_char: str | None = None) -> str:
        """返回有效字面。赖子需要指定target_char。"""
        if self.is_wild:
            if target_char is None:
                return "赖"
            return target_char
        return self.char

    # ---------- 输出 ----------

    def __repr__(self):
        gold_str = "花" if self.is_gold else "皮"
        jing_str = f"[{gold_str}]" if self.is_jing else ""
        wild_str = "[赖]" if self.is_wild else ""
        return f"Card({self.id}:{self.char}{jing_str}{wild_str})"

    def __eq__(self, other):
        if isinstance(other, Card):
            return self.id == other.id
        return NotImplemented

    def __hash__(self):
        return self.id

    def to_dict(self):
        return {
            "id": self.id,
            "char": self.char,
            "char_type": self.char_type.value,
            "color": self.color.value,
            "is_gold": self.is_gold,
            "jing_sub_type": self.jing_sub_type.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Card":
        return cls(
            id_=d["id"],
            char=d["char"],
            char_type=CharType(d["char_type"]),
            color=Color(d["color"]),
            is_gold=d.get("is_gold", False),
            jing_sub_type=JingSubType(d.get("jing_sub_type", "none")),
        )


# ============================================================
# 牌组管理
# ============================================================

def create_deck() -> list[Card]:
    """
    生成完整112张牌组。
    22种字面各5张(共110张) + 2张赖子。
    精牌(乙三五七九)每种2张花精+3张皮精。
    """
    cards: list[Card] = []
    card_id = 0

    for char, (char_type, color) in CHAR_ATTRIBUTES.items():
        if char in JING_CHARS:
            # 精牌：2张花精 + 3张皮精
            for i in range(2):
                cards.append(Card(card_id, char, char_type, color,
                                  is_gold=True, jing_sub_type=JingSubType.FLOWER))
                card_id += 1
            for i in range(3):
                cards.append(Card(card_id, char, char_type, color,
                                  is_gold=False, jing_sub_type=JingSubType.SKIN))
                card_id += 1
        else:
            # 普通牌：5张相同
            for i in range(5):
                cards.append(Card(card_id, char, char_type, color))
                card_id += 1

    # 2张赖子
    for i in range(2):
        cards.append(Card(card_id, "赖", CharType.WILD, Color.RED))
        card_id += 1

    assert len(cards) == 112, f"Expected 112 cards, got {len(cards)}"
    return cards


def shuffle_deck(cards: list[Card]) -> list[Card]:
    """Fisher-Yates洗牌"""
    deck = cards[:]
    for i in range(len(deck) - 1, 0, -1):
        j = random.randint(0, i)
        deck[i], deck[j] = deck[j], deck[i]
    return deck


def deal(deck: list[Card]) -> tuple[dict[int, list[Card]], list[Card]]:
    """
    发牌。
    返回: (player_cards, draw_pile)
    player_cards: {0: [26张], 1: [25张], 2: [25张]}
    draw_pile: 剩余牌（余牌池）
    """
    assert len(deck) == 112

    # 顺序: 庄(0)→下家(1)→上家(2)，循环发牌
    hands = {0: [], 1: [], 2: []}
    idx = 0
    for i in range(25):
        for p in range(3):
            hands[p].append(deck[idx])
            idx += 1
    # 庄家多发一张
    hands[0].append(deck[idx])
    idx += 1

    draw_pile = deck[idx:]
    return hands, draw_pile


def sort_cards(cards: list[Card]) -> list[Card]:
    """按字面类型和字面排选手牌"""
    order = {"上": 0, "大": 1, "人": 2, "可": 3, "知": 4, "礼": 5,
             "三": 6, "五": 7, "七": 8,
             "化": 9, "千": 10, "孔": 11, "乙": 12, "已": 13,
             "二": 14, "四": 15, "六": 16, "八": 17, "九": 18,
             "十": 19, "子": 20, "土": 21, "赖": 22}
    return sorted(cards, key=lambda c: order.get(c.char, 99))


def cards_to_char_list(cards: list[Card]) -> list[str]:
    """获取牌的字面列表"""
    return [c.char for c in cards]
