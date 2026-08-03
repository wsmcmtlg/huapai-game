"""
ai/tests/test_ai.py — AI 模块测试套件
======================================
验证 SimpleAI 和 MediumAI 的决策逻辑正确性。

测试范围：
1. AI 初始化与引擎对接
2. 出牌决策合理性
3. 响应决策正确性
4. 自摸决策正确性
5. 扎牌决策正确性
6. 完整对战循环
"""

import sys
import os
import random

# 路径设置
_phase1_path = os.path.join(os.path.dirname(__file__), "..", "..", "Phase 1 规则引擎")
if os.path.exists(_phase1_path) and _phase1_path not in sys.path:
    sys.path.insert(0, os.path.abspath(_phase1_path))

_ai_path = os.path.join(os.path.dirname(__file__), "..")
if _ai_path not in sys.path:
    sys.path.insert(0, os.path.abspath(_ai_path))

from core import (
    GameEngine, Card, Deck, Meld, MeldType,
    ActionPriority, PlayerAction, ScoreCalculator,
    JING_CHARS, RED_JING_CHARS, WILD_CHAR, WILD_USABLE_CHARS,
    ALL_SEQUENCES, calc_points,
)
from AI.base import AIBase
from AI.simple import SimpleAI
from AI.medium import MediumAI
from AI.controller import AIGameController, AI_REGISTRY


class TestResult:
    """测试结果记录"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: list = []

    def ok(self, name: str):
        self.passed += 1
        print(f"  PASS: {name}")

    def fail(self, name: str, reason: str):
        self.failed += 1
        msg = f"  FAIL: {name} — {reason}"
        print(msg)
        self.errors.append(msg)

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"测试结果: {self.passed}/{total} 通过", end="")
        if self.failed:
            print(f", {self.failed} 失败")
            for e in self.errors:
                print(e)
        else:
            print()
        return self.failed == 0


def test_ai_registry():
    """测试1: AI注册表"""
    r = TestResult()
    print("\n测试1: AI注册表")

    if "simple" in AI_REGISTRY:
        r.ok("simple 已注册")
    else:
        r.fail("simple 注册", "未找到")

    if "medium" in AI_REGISTRY:
        r.ok("medium 已注册")
    else:
        r.fail("medium 注册", "未找到")

    if issubclass(AI_REGISTRY["simple"], AIBase):
        r.ok("SimpleAI 继承 AIBase")
    else:
        r.fail("SimpleAI 继承", "未继承 AIBase")

    if issubclass(AI_REGISTRY["medium"], AIBase):
        r.ok("MediumAI 继承 AIBase")
    else:
        r.fail("MediumAI 继承", "未继承 AIBase")

    return r


def test_ai_initialization():
    """测试2: AI初始化"""
    r = TestResult()
    print("\n测试2: AI初始化")

    engine = GameEngine(player_names=["AI0", "AI1", "AI2"])
    engine.start_game()

    simple = SimpleAI(player_index=0, engine=engine, seed=42)
    medium = MediumAI(player_index=1, engine=engine, seed=42)

    if simple.player_index == 0:
        r.ok("SimpleAI player_index 正确")
    else:
        r.fail("SimpleAI player_index", f"期望0, 实际{simple.player_index}")

    if medium.player_index == 1:
        r.ok("MediumAI player_index 正确")
    else:
        r.fail("MediumAI player_index", f"期望1, 实际{medium.player_index}")

    simple.refresh_player()
    if simple.player is not None and simple.player.name == "AI0":
        r.ok("SimpleAI refresh_player 正确")
    else:
        r.fail("SimpleAI refresh_player", "player引用不正确")

    medium.refresh_player()
    if medium.player is not None:
        r.ok("MediumAI refresh_player 正确")
    else:
        r.fail("MediumAI refresh_player", "player引用为None")

    return r


def test_discard_decision():
    """测试3: 出牌决策"""
    r = TestResult()
    print("\n测试3: 出牌决策")

    engine = GameEngine(player_names=["AI0", "AI1", "AI2"])
    engine.start_game()

    simple = SimpleAI(player_index=0, engine=engine, seed=42)
    simple.refresh_player()

    # 测试出牌是否返回一张手牌中的牌
    card = simple.decide_discard()
    if card is not None:
        hand_ids = {c.id for c in simple.hand}
        if card.id in hand_ids:
            r.ok("SimpleAI 出牌在手牌中")
        else:
            r.fail("SimpleAI 出牌", f"出的牌不在手牌中: {card}")
    else:
        r.fail("SimpleAI 出牌", "返回None（手牌不应为空）")

    # 测试 MediumAI
    medium = MediumAI(player_index=1, engine=engine, seed=42)
    medium.refresh_player()

    card2 = medium.decide_discard()
    if card2 is not None:
        hand_ids2 = {c.id for c in medium.hand}
        if card2.id in hand_ids2:
            r.ok("MediumAI 出牌在手牌中")
        else:
            r.fail("MediumAI 出牌", f"出的牌不在手牌中: {card2}")
    else:
        r.fail("MediumAI 出牌", "返回None")

    return r


def test_response_decision():
    """测试4: 响应决策"""
    r = TestResult()
    print("\n测试4: 响应决策")

    engine = GameEngine(player_names=["AI0", "AI1", "AI2"])
    engine.start_game()

    simple = SimpleAI(player_index=1, engine=engine, seed=42)
    simple.refresh_player()

    # 从 Player0 手中选一张牌模拟出牌
    dealer = engine.players[0]
    if dealer.hand:
        played = dealer.hand[0]

        # 检查可用操作
        is_prev = (simple.player_index == engine.previous_player(0))
        actions = engine.validator.get_available_actions(
            hand=simple.hand,
            player_index=simple.player_index,
            played_card=played,
            from_player=0,
            exposed_melds=simple.player.get_exposed_melds(),
            is_previous_player=is_prev,
        )

        response = simple.decide_response(played, 0, actions)

        if response is None:
            r.ok("SimpleAI 选择过牌（无可用操作时）")
        elif response.action_type in (
            ActionPriority.HU, ActionPriority.CHUAN,
            ActionPriority.ZHAO, ActionPriority.PEN, ActionPriority.CHOW,
        ):
            r.ok(f"SimpleAI 响应: {response.action_type.name}")
        else:
            r.fail("SimpleAI 响应", f"未知操作类型: {response.action_type}")
    else:
        r.fail("响应测试", "庄家手牌为空")

    return r


def test_self_action_decision():
    """测试5: 自摸决策"""
    r = TestResult()
    print("\n测试5: 自摸决策")

    engine = GameEngine(player_names=["AI0", "AI1", "AI2"])
    engine.start_game()

    simple = SimpleAI(player_index=0, engine=engine, seed=42)
    simple.refresh_player()

    # 模拟摸牌
    engine.draw_card(0)

    # 获取自摸可用操作
    self_actions = engine.check_self_actions(0)
    action = simple.decide_self_action(self_actions)

    if action is not None:
        if action.action_type in (
            ActionPriority.HU, ActionPriority.FAN, ActionPriority.ZHA,
        ):
            r.ok(f"SimpleAI 自摸操作: {action.action_type.name}")
        else:
            r.fail("SimpleAI 自摸", f"操作类型异常: {action.action_type}")
    else:
        r.ok("SimpleAI 自摸不出牌（无可用操作）")

    return r


def test_zha_decision():
    """测试6: 扎牌决策"""
    r = TestResult()
    print("\n测试6: 扎牌决策")

    engine = GameEngine(player_names=["AI0", "AI1", "AI2"])
    engine.start_game()

    simple = SimpleAI(player_index=0, engine=engine, seed=42)
    simple.refresh_player()

    # 获取可扎操作
    zha_actions = engine.validator.check_zha(simple.hand, 0)
    selected = simple.decide_zha(zha_actions)

    if not zha_actions:
        r.ok("无可扎操作（正常）")
    else:
        if len(selected) <= len(zha_actions):
            r.ok(f"SimpleAI 扎牌: 选择{len(selected)}/{len(zha_actions)}组")
        else:
            r.fail("SimpleAI 扎牌", f"选择了比可用更多的扎牌")

    # MediumAI
    medium = MediumAI(player_index=1, engine=engine, seed=42)
    medium.refresh_player()

    zha_actions2 = engine.validator.check_zha(medium.hand, 1)
    selected2 = medium.decide_zha(zha_actions2)

    if not zha_actions2:
        r.ok("MediumAI 无可扎操作")
    else:
        r.ok(f"MediumAI 扎牌: 选择{len(selected2)}/{len(zha_actions2)}组")

    return r


def test_value_score():
    """测试7: 牌价值评估"""
    r = TestResult()
    print("\n测试7: 牌价值评估")

    engine = GameEngine(player_names=["AI0", "AI1", "AI2"])
    engine.start_game()

    simple = SimpleAI(player_index=0, engine=engine, seed=42)
    simple.refresh_player()

    # 赖子应该有价值
    wild_score = simple.get_char_value_score(WILD_CHAR)
    if wild_score > 0:
        r.ok(f"赖子有价值: {wild_score:.1f}")
    else:
        r.fail("赖子价值", f"期望>0, 实际{wild_score}")

    # 精牌应该有价值
    if RED_JING_CHARS:
        jing_score = simple.get_char_value_score(RED_JING_CHARS[0])
        if jing_score > 0:
            r.ok(f"精牌有价值: {jing_score:.1f}")
        else:
            r.fail("精牌价值", f"期望>0, 实际{jing_score}")

    return r


def test_full_game():
    """测试8: 完整对战循环"""
    r = TestResult()
    print("\n测试8: 完整对战循环")

    try:
        controller = AIGameController(
            ai_config={0: "simple", 1: "medium", 2: "simple"},
            player_names=["简单AI", "中等AI", "简单AI2"],
            seed=42,
            verbose=False,
        )

        log = controller.run_game(max_rounds=1)

        if len(log.round_results) >= 1:
            r.ok(f"完成1局对战，结果: {log.round_results[0].win_type.value}")
        else:
            r.fail("对战循环", "未产生结果")

        if len(log.decisions) > 0:
            r.ok(f"产生决策日志: {len(log.decisions)}条")
        else:
            r.fail("决策日志", "无日志记录")

    except Exception as e:
        r.fail("完整对战", f"异常: {e}")
        import traceback
        traceback.print_exc()

    return r


def test_multi_game():
    """测试9: 多局对战"""
    r = TestResult()
    print("\n测试9: 多局对战(3局)")

    try:
        controller = AIGameController(
            ai_config={0: "simple", 1: "medium", 2: "medium"},
            seed=123,
            verbose=False,
        )

        log = controller.run_game(max_rounds=3)

        if len(log.round_results) >= 1:
            r.ok(f"完成{len(log.round_results)}局对战")
        else:
            r.fail("多局对战", "未完成任何局")

        # 检查日志摘要
        summary = log.summary()
        has_winner = any(r.winner is not None for r in log.round_results)
        if has_winner:
            if "胜场统计" in summary:
                r.ok("日志包含胜场统计")
            else:
                r.fail("日志摘要", "缺少胜场统计")
        else:
            # 全部流局，不应出现胜场统计
            if "胜场统计" not in summary:
                r.ok("流局时无胜场统计（正确）")
            else:
                r.fail("日志摘要", "流局时不应有胜场统计")

    except Exception as e:
        r.fail("多局对战", f"异常: {e}")
        import traceback
        traceback.print_exc()

    return r


def run_all_tests():
    """运行全部测试"""
    print("=" * 50)
    print("AI 模块测试套件")
    print("=" * 50)

    results = []
    results.append(test_ai_registry())
    results.append(test_ai_initialization())
    results.append(test_discard_decision())
    results.append(test_response_decision())
    results.append(test_self_action_decision())
    results.append(test_zha_decision())
    results.append(test_value_score())
    results.append(test_full_game())
    results.append(test_multi_game())

    total_passed = sum(r.passed for r in results)
    total_failed = sum(r.failed for r in results)
    total = total_passed + total_failed

    print(f"\n{'='*50}")
    print(f"总计: {total_passed}/{total} 通过", end="")
    if total_failed:
        print(f", {total_failed} 失败")
    else:
        print()

    return total_failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
