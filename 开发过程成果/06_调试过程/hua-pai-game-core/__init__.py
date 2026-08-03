"""
花牌游戏 - 核心模块包
"""

from .card import Card, create_deck, shuffle_deck, deal, sort_cards
from .player import Player
from .engine import GameEngine, GameState
from .scoring import (
    calc_sequence_score, calc_pen_score, calc_triplet_score,
    calc_zhao_score, calc_zha_score, calc_chuan_score, calc_fan_score,
    calc_total_score, find_best_zhu_jing
)
from .analyzer import (
    check_ting, check_hu_with_card,
    can_pen, can_zhao, can_fan_from_discard, can_fan_from_hand,
    get_zha_opportunities, get_chuan_opportunities
)
from .melds import (
    MeldType, FanType, WinType, CharType, Color, JingSubType,
    Action, ALL_SEQUENCES, JING_CHARS, Meld
)

__all__ = [
    "Card", "create_deck", "shuffle_deck", "deal", "sort_cards",
    "Player", "GameEngine", "GameState",
    "calc_sequence_score", "calc_pen_score", "calc_triplet_score",
    "calc_zhao_score", "calc_zha_score", "calc_chuan_score", "calc_fan_score",
    "calc_total_score", "find_best_zhu_jing",
    "check_ting", "check_hu_with_card",
    "can_pen", "can_zhao", "can_fan_from_discard", "can_fan_from_hand",
    "get_zha_opportunities", "get_chuan_opportunities",
    "MeldType", "FanType", "WinType", "CharType", "Color", "JingSubType",
    "Action", "ALL_SEQUENCES", "JING_CHARS", "Meld",
]
