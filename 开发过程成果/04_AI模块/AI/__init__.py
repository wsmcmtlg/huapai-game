"""
AI — 湖北公安花牌 AI 策略机器人
================================
提供不同难度级别的 AI 玩家策略，可与 GameEngine 无缝对接。

模块结构：
  base.py       — AI基类(AIBase)，定义决策接口和公共工具方法
  simple.py     — 简单AI(SimpleAI)，基于规则启发式的初级策略
  medium.py     — 中级AI(MediumAI)，具备基础听牌判断和胡牌追求
  __init__.py   — 包导出

用法示例：
    from core import GameEngine
    from ai import SimpleAI

    engine = GameEngine(player_names=["人类", "AI-简单", "AI-中等"])
    ai_player = SimpleAI(player_index=1, engine=engine)
    
    # 出牌决策
    card_to_discard = ai_player.decide_discard()
    
    # 响应决策
    action = ai_player.decide_response(played_card, from_player)
"""

from .base import AIBase
from .simple import SimpleAI
from .medium import MediumAI

__all__ = [
    "AIBase",
    "SimpleAI",
    "MediumAI",
]

__version__ = "1.0.0"
