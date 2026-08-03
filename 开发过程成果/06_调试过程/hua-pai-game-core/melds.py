"""
花牌游戏 - 牌型定义模块
定义所有牌型枚举、顺子表、以及相关常量。
"""

from enum import Enum
from typing import NamedTuple


# ============================================================
# 枚举定义
# ============================================================

class CharType(Enum):
    """字面类型"""
    RED = "red"               # 红牌：上大可人知礼
    RED_JING = "red_jing"     # 红精：三七五
    BLACK = "black"           # 黑牌：化千孔已二四六八十子土
    BLACK_JING = "black_jing" # 黑精：乙九
    WILD = "wild"             # 赖子


class Color(Enum):
    RED = "red"
    BLACK = "black"


class JingSubType(Enum):
    """精牌子类型"""
    NONE = "none"
    FLOWER = "flower"   # 花精（描金）
    SKIN = "skin"       # 皮精（非描金）


class MeldType(Enum):
    """牌型"""
    SEQUENCE = "sequence"  # 顺子
    TRIPLET = "triplet"    # 刻子（坎牌）
    PEN = "pen"            # 对牌（碰牌）
    ZHAO = "zhao"          # 招牌
    ZHA = "zha"            # 扎牌
    CHUAN = "chuan"        # 穿牌
    FAN = "fan"            # 泛牌


class FanType(Enum):
    """泛牌触发情形"""
    FROM_DISCARD = "from_discard"  # 情形一：扎牌+旁家出牌
    FROM_HAND = "from_hand"        # 情形二：招牌+手中牌


class WinType(Enum):
    """胡牌方式"""
    TIAN_HU = "tian_hu"
    DI_HU = "di_hu"
    ZI_MO = "zi_mo"
    ZHUO_TONG = "zhuo_tong"
    HUANG_ZHUANG = "huang"


class Action(Enum):
    """玩家可执行的操作"""
    DISCARD = "discard"
    PEN = "pen"
    ZHAO = "zhao"
    ZHA = "zha"
    CHUAN = "chuan"
    FAN = "fan"
    SWAP_ZHA = "swap_zha"
    HU = "hu"
    PASS = "pass"


# ============================================================
# 顺子定义
# ============================================================

# 六种固定顺子
FIXED_SEQUENCES = [
    ("上", "大", "人"),   # 红牌顺子
    ("可", "知", "礼"),   # 红牌顺子
    ("化", "千", "三"),   # 混合顺子
    ("孔", "乙", "已"),   # 混合顺子
    ("七", "十", "土"),   # 混合顺子
    ("八", "九", "子"),   # 黑牌顺子
]

# 数字顺子（一二三 ~ 八九十）
NUMBER_CHARS = ["二", "三", "四", "五", "六", "七", "八", "九", "十"]
NUMBER_SEQUENCES = []
for i in range(len(NUMBER_CHARS) - 2):
    NUMBER_SEQUENCES.append(tuple(NUMBER_CHARS[i:i + 3]))

# 所有顺子
ALL_SEQUENCES = FIXED_SEQUENCES + NUMBER_SEQUENCES


class Meld(NamedTuple):
    """牌型组合"""
    meld_type: MeldType
    char: str                    # 牌型对应的字面（坎/招/扎/穿/泛为该字面）
    cards: list                  # 组成牌型的牌列表
    is_open: bool = False        # 是否明牌（对牌、招牌、泛牌需要明示）
    fan_type: FanType | None = None  # 泛牌类型


# ============================================================
# 字面属性常量
# ============================================================

# 每个字面的类型和颜色
CHAR_ATTRIBUTES = {
    # 红牌
    "上": (CharType.RED, Color.RED),
    "大": (CharType.RED, Color.RED),
    "人": (CharType.RED, Color.RED),
    "可": (CharType.RED, Color.RED),
    "知": (CharType.RED, Color.RED),
    "礼": (CharType.RED, Color.RED),
    # 红精
    "三": (CharType.RED_JING, Color.RED),
    "五": (CharType.RED_JING, Color.RED),
    "七": (CharType.RED_JING, Color.RED),
    # 黑牌
    "化": (CharType.BLACK, Color.BLACK),
    "千": (CharType.BLACK, Color.BLACK),
    "孔": (CharType.BLACK, Color.BLACK),
    "已": (CharType.BLACK, Color.BLACK),
    "二": (CharType.BLACK, Color.BLACK),
    "四": (CharType.BLACK, Color.BLACK),
    "六": (CharType.BLACK, Color.BLACK),
    "八": (CharType.BLACK, Color.BLACK),
    "十": (CharType.BLACK, Color.BLACK),
    "子": (CharType.BLACK, Color.BLACK),
    "土": (CharType.BLACK, Color.BLACK),
    # 黑精
    "乙": (CharType.BLACK_JING, Color.BLACK),
    "九": (CharType.BLACK_JING, Color.BLACK),
}

# 精牌字面集合
JING_CHARS = {"乙", "三", "五", "七", "九"}
RED_JING_CHARS = {"三", "五", "七"}
BLACK_JING_CHARS = {"乙", "九"}

# 赖子可通配的字面
WILD_TARGETS = {"三", "五", "七"}

# 顺子集合（用frozenset便于快速查找）
SEQUENCE_SET = {frozenset(s) for s in ALL_SEQUENCES}
