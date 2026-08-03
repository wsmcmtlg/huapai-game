"""
ai/controller.py — AI 游戏控制器（增强版 v2）
============================================
将 AI 策略与 GameEngine 连接，实现全自动 AI 对战 或 人机混合模式。

v2 修复：
- _handle_discard: 人类出牌时 on_human_input 通过 HumanInputGate 阻塞等待，
  不再在 controller 层做 None 检查跳过，完全依赖回调的阻塞语义
- _handle_zha_phase: 修复重复调用 finish_dealing 的问题
- 确保所有状态转换在 engine 和 controller 之间一致
"""

from __future__ import annotations

import random
import time
import sys
import os
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# 确保能导入 core 包
_phase1_path = os.path.join(os.path.dirname(__file__), "..", "Phase 1 规则引擎")
if os.path.exists(_phase1_path) and _phase1_path not in sys.path:
    sys.path.insert(0, os.path.abspath(_phase1_path))

from core.engine import GameEngine, EngineState, RoundResult
from core.actions import PlayerAction, ActionPriority, ActionValidator
from core.card import Card
from core.melds import PLAYER_COUNT, MeldType
from core.rules import GameRules, DEFAULT_RULES

# 相对导入（作为 ai 包的一部分时）
from .base import AIBase
from .simple import SimpleAI
from .medium import MediumAI


# ============================================================
# AI 注册表
# ============================================================

AI_REGISTRY: Dict[str, type] = {
    "simple": SimpleAI,
    "medium": MediumAI,
}


# ============================================================
# 对战日志
# ============================================================

@dataclass
class DecisionLog:
    """单次决策日志"""
    round_num: int = 0
    player_index: int = 0
    decision_type: str = ""
    detail: str = ""


@dataclass
class GameLog:
    """游戏日志"""
    round_results: List[RoundResult] = field(default_factory=list)
    decisions: List[DecisionLog] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    def add_decision(self, log: DecisionLog) -> None:
        self.decisions.append(log)

    def summary(self) -> str:
        duration = self.end_time - self.start_time if self.end_time > self.start_time else 0
        lines = [f"游戏结束 | 共 {len(self.round_results)} 局 | 耗时 {duration:.1f}s"]
        for i, r in enumerate(log.round_results):
            lines.append(f"  第{i+1}局: {r}")
        return "\n".join(lines)


# ============================================================
# AIGameController
# ============================================================

class AIGameController:
    """AI 游戏控制器

    管理 AI 策略和 GameEngine，驱动完整的游戏循环。

    当 ai_config 未包含某个玩家索引时，该玩家为人类玩家。
    人类玩家的操作通过 on_human_input 回调获取。
    回调签名: on_human_input(action_type: str, context: Dict) -> Any
    - action_type: "discard" / "response" / "zha" / "self_check"
    - context: {"player_index": int, "available": [...], ...}
    - 返回值: Card(出牌) / PlayerAction / str("pass"/"hu"/"pen"/...) / None(跳过)

    注意：on_human_input 由 LocalBridge.HumanInputGate 驱动时会阻塞等待，
    返回值不会是 None（超时才返回 None）。
    """

    def __init__(
        self,
        ai_config: Optional[Dict[int, str]] = None,
        player_names: Optional[List[str]] = None,
        rules: Optional[GameRules] = None,
        seed: Optional[int] = None,
        verbose: bool = False,
    ):
        self.ai_config = ai_config or {}
        self.player_names = player_names
        self.rules = rules or DEFAULT_RULES
        self.verbose = verbose
        self._seed = seed

        if seed is not None:
            random.seed(seed)

        names = player_names or ["玩家0", "玩家1", "玩家2"]
        self.engine = GameEngine(player_names=names, rules=self.rules)

        # 初始化 AI 玩家
        self.ai_players: Dict[int, AIBase] = {}
        self.human_players: set = set()

        if ai_config:
            for pid, strategy_name in ai_config.items():
                strategy_class = AI_REGISTRY.get(strategy_name)
                if strategy_class is None:
                    raise ValueError(
                        f"未知AI策略: {strategy_name}，"
                        f"可选: {list(AI_REGISTRY.keys())}"
                    )
                self.ai_players[pid] = strategy_class(
                    player_index=pid,
                    engine=self.engine,
                    seed=seed,
                )

        # 确定人类玩家
        for i in range(PLAYER_COUNT):
            if i not in self.ai_players:
                self.human_players.add(i)

        # 游戏日志
        self.game_log = GameLog()

        # 人类输入回调（由 LocalBridge 设置）
        self.on_human_input: Optional[Callable[[str, Dict[str, Any]], Any]] = None

        # 游戏控制
        self._stop_flag = False
        self._pending_actions: Optional[Dict[int, List[PlayerAction]]] = None
        self._pending_self_actions: Optional[Tuple[int, List[PlayerAction]]] = None

    def _refresh_ai_players(self) -> None:
        """刷新 AI 玩家的内部引用（新一局开始后）"""
        for ai in self.ai_players.values():
            ai.refresh_player()

    # ================================================================
    # 主循环
    # ================================================================

    def run_game(self, max_rounds: int = 1) -> GameLog:
        """运行完整的游戏"""
        self.game_log = GameLog()
        self.game_log.start_time = time.time()
        self._stop_flag = False

        self.engine.start_game()
        self._refresh_ai_players()

        if self.verbose:
            self._print_game_start()

        round_count = 0
        while round_count < max_rounds and not self._stop_flag:
            round_count += 1
            result = self._run_one_round()

            if result:
                self.game_log.round_results.append(result)
                if self.verbose:
                    self._print_round_result(result)

                # 非流局时轮换庄家，继续下一局
                if result.win_type.value != "huang":
                    self.engine.rotate_dealer()
                    self._refresh_ai_players()

        self.game_log.end_time = time.time()

        if self.verbose:
            print("\n" + "=" * 60)
            print(self.game_log.summary())

        return self.game_log

    def _run_one_round(self) -> Optional[RoundResult]:
        """运行一局游戏

        完整流程：
        发牌 → 反向扎牌 → 庄家天胡检查 → 打牌循环 → 结算
        """
        self.engine.finish_dealing()

        # 反向扎牌阶段
        zha_actions = self._handle_zha_phase()
        if self.verbose and zha_actions:
            self._print_zha_actions(zha_actions)

        # 庄家天胡检查
        tian_hu = self.engine.check_dealer_tian_hu()
        if tian_hu:
            return tian_hu

        # 庄家出牌
        self.engine.start_dealer_discard()

        # 打牌循环
        max_turns = 200
        turn_count = 0

        while turn_count < max_turns and not self._stop_flag:
            turn_count += 1

            # 流局检查
            if self.engine.check_liuju():
                if self.verbose:
                    print("余牌耗尽，流局！")
                return self.engine.handle_liuju()

            current_state = self.engine.state

            if current_state in (EngineState.DEALER_DISCARD,
                                 EngineState.PLAYER_DISCARD,
                                 EngineState.PEN_DISCARD):
                result = self._handle_discard()
                if result:
                    return result

            elif current_state == EngineState.WAITING_RESPONSE:
                result = self._handle_response()
                if result:
                    return result
                self.engine.advance_turn()

            elif current_state == EngineState.DRAW_CARD:
                self._handle_draw()

            elif current_state == EngineState.SELF_CHECK:
                result = self._handle_self_check()
                if result:
                    return result
                self.engine.state = EngineState.PLAYER_DISCARD

            elif current_state == EngineState.GAME_OVER:
                break

        if turn_count >= max_turns:
            if self.verbose:
                print("超过最大轮数，流局！")
            return self.engine.handle_liuju()

        return None

    # ================================================================
    # 阶段处理
    # ================================================================

    def _handle_discard(self) -> Optional[RoundResult]:
        """处理出牌阶段

        AI 玩家：自动决策出牌
        人类玩家：通过 on_human_input 回调获取出牌（回调内部会阻塞等待）
        """
        current = self.engine.get_current_player()
        card = None

        if current.index in self.ai_players:
            ai = self.ai_players[current.index]
            card = ai.decide_discard()
            if card is None:
                if self.verbose:
                    print(f"  {current.name} 无法出牌")
                return None
        else:
            # 人类玩家 — 调用回调，回调内部通过 HumanInputGate.wait() 阻塞
            if self.on_human_input:
                card = self.on_human_input("discard", {
                    "player_index": current.index,
                    "hand": list(current.hand),  # 传入手牌供 UI 显示
                })
            else:
                if self.verbose:
                    print(f"  {current.name} (人类) 无回调，跳过")
                return None

        if card is None:
            # 超时或取消
            return None

        # 执行出牌
        success = self.engine.play_card(current.index, card)
        if not success:
            if self.verbose:
                print(f"  {current.name} 出牌失败: {card}")
            return None

        if self.verbose:
            print(f"  {current.name} 出牌: {card}")

        # 通知出牌（通过 engine.on_action）
        if self.engine.on_action:
            self.engine.on_action(PlayerAction(
                action_type=ActionPriority.PASS,
                cards=[card],
                source_player=current.index,
                description=f"出 {card}",
            ))

        # 更新状态管理器
        self._update_state_notify()

        # 检查旁家响应
        actions_map = self.engine.check_other_players_actions(card, current.index)

        if actions_map:
            self.engine.state = EngineState.WAITING_RESPONSE
            self._pending_actions = actions_map
            return None

        self.engine.advance_turn()
        return None

    def _handle_response(self) -> Optional[RoundResult]:
        """处理旁家响应"""
        if self._pending_actions is None:
            return None

        actions_map = self._pending_actions
        ai_responses: Dict[int, List[PlayerAction]] = {}

        for pid, actions in actions_map.items():
            if pid in self.ai_players:
                ai = self.ai_players[pid]
                played_card = self.engine.played_card
                from_player = self.engine.last_played_by
                if played_card:
                    response = ai.decide_response(played_card, from_player, actions)
                    if response:
                        ai_responses[pid] = [response]
            else:
                # 人类玩家 — 回调内部阻塞等待
                if self.on_human_input:
                    human_result = self.on_human_input("response", {
                        "player_index": pid,
                        "available": actions,
                        "played_card": self.engine.played_card,
                    })
                    if human_result is not None and isinstance(human_result, PlayerAction):
                        ai_responses[pid] = [human_result]
                    elif isinstance(human_result, str) and human_result != "pass":
                        type_name_map = {
                            ActionPriority.HU: "hu", ActionPriority.CHUAN: "chuan",
                            ActionPriority.ZHAO: "zhao", ActionPriority.PEN: "pen",
                            ActionPriority.CHOW: "chow",
                        }
                        for a in actions:
                            if type_name_map.get(a.action_type) == human_result:
                                ai_responses[pid] = [a]
                                break

        self._pending_actions = None

        if ai_responses:
            final_action = self._resolve_responses(ai_responses)
            if final_action:
                result = self.engine.execute_action(final_action)
                if self.verbose:
                    player = self.engine.players[final_action.source_player]
                    print(f"  {player.name} {final_action.description}")

                # 通知操作
                if self.engine.on_action and result is None:
                    self.engine.on_action(final_action)

                # 更新状态
                self._update_state_notify()
                return result

        # 全部过
        return None

    def _resolve_responses(self, responses: Dict[int, List[PlayerAction]]) -> Optional[PlayerAction]:
        """解决多个玩家响应冲突"""
        from_player = self.engine.last_played_by
        candidates = []
        for pid, actions in responses.items():
            for action in actions:
                if action.action_type != ActionPriority.PASS:
                    candidates.append((pid, action))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1].action_type, reverse=True)
        best_priority = candidates[0][1].action_type
        top_candidates = [(pid, a) for pid, a in candidates if a.action_type == best_priority]

        if len(top_candidates) == 1:
            return top_candidates[0][1]

        def distance(pid):
            diff = (from_player - pid) % 3
            return diff if diff != 0 else 3

        top_candidates.sort(key=lambda x: distance(x[0]))
        return top_candidates[0][1]

    def _handle_draw(self) -> None:
        """处理摸牌"""
        current = self.engine.get_current_player()
        card = self.engine.draw_card(current.index)

        if card:
            if self.verbose:
                print(f"  {current.name} 摸牌: {card}")

            self_actions = self.engine.check_self_actions(current.index)
            if self_actions:
                self.engine.state = EngineState.SELF_CHECK
                self._pending_self_actions = (current.index, self_actions)
            else:
                self.engine.state = EngineState.PLAYER_DISCARD

            self._update_state_notify()
        else:
            self.engine.state = EngineState.GAME_OVER

    def _handle_self_check(self) -> Optional[RoundResult]:
        """处理自摸检查"""
        if self._pending_self_actions is None:
            return None

        player_idx, self_actions = self._pending_self_actions
        player = self.engine.players[player_idx]

        if player_idx in self.ai_players:
            ai = self.ai_players[player_idx]
            action = ai.decide_self_action(self_actions)
            if action:
                result = self.engine.execute_action(action)
                if self.verbose:
                    print(f"  {player.name} {action.description}")
                return result
        else:
            # 人类玩家
            if self.on_human_input:
                human_result = self.on_human_input("self_check", {
                    "player_index": player_idx,
                    "available": self_actions,
                })
                if human_result is not None and isinstance(human_result, PlayerAction):
                    result = self.engine.execute_action(human_result)
                    if self.verbose:
                        print(f"  {player.name} {human_result.description}")
                    return result
                elif isinstance(human_result, str) and human_result != "pass":
                    type_name_map = {
                        ActionPriority.HU: "hu", ActionPriority.CHUAN: "chuan",
                        ActionPriority.ZHAO: "zhao", ActionPriority.PEN: "pen",
                        ActionPriority.CHOW: "chow", ActionPriority.ZHA: "zha",
                        ActionPriority.FAN: "fan",
                    }
                    for a in self_actions:
                        if type_name_map.get(a.action_type) == human_result:
                            result = self.engine.execute_action(a)
                            if self.verbose:
                                print(f"  {player.name} {a.description}")
                            return result

        self._pending_self_actions = None
        return None

    def _handle_zha_phase(self) -> List[PlayerAction]:
        """处理反向扎牌阶段

        AI 玩家：自动决策是否扎牌
        人类玩家：通过 on_human_input 决定（回调内部阻塞等待）

        注意：不再在此方法中调用 finish_dealing()，因为 _run_one_round
        开头已经调用过。engine 的状态流转为：
        start_game(DEALING) → finish_dealing(ZHA_PHASE) → zha_phase → (此方法) → check_dealer_tian_hu
        """
        all_actions: List[PlayerAction] = []

        for player_idx in self.engine.zha_phase_players():
            player = self.engine.players[player_idx]

            if player_idx in self.ai_players:
                ai = self.ai_players[player_idx]
                zha_list = self.engine.validator.check_zha(player.hand, player_idx)
                selected = ai.decide_zha(zha_list)
                for action in selected:
                    from core.scoring import Meld as ScoringMeld
                    meld = ScoringMeld(
                        meld_type=MeldType.ZHA,
                        cards=tuple(action.cards),
                        is_open=False,
                    )
                    player.add_meld(meld)
                    card = self.engine.deck.draw_bottom()
                    if card:
                        player.add_card(card)
                    all_actions.append(action)
                    if self.verbose:
                        print(f"  [扎牌] {player.name}: {action.description}")
            else:
                # 人类玩家
                zha_list = self.engine.validator.check_zha(player.hand, player_idx)
                if zha_list and self.on_human_input:
                    human_result = self.on_human_input("zha", {
                        "player_index": player_idx,
                        "available": zha_list,
                    })
                    if human_result is not None and isinstance(human_result, list):
                        for action in human_result:
                            from core.scoring import Meld as ScoringMeld
                            meld = ScoringMeld(
                                meld_type=MeldType.ZHA,
                                cards=tuple(action.cards),
                                is_open=False,
                            )
                            player.add_meld(meld)
                            card = self.engine.deck.draw_bottom()
                            if card:
                                player.add_card(card)
                            all_actions.append(action)
                            if self.verbose:
                                print(f"  [扎牌] {player.name}: {action.description}")

        # 更新状态
        self._update_state_notify()
        return all_actions

    def _update_state_notify(self) -> None:
        """通知状态更新（让 UI 刷新）"""
        if self.engine.on_state_change:
            self.engine.on_state_change(self.engine.state, self.engine.get_game_info())

    # ================================================================
    # 输出
    # ================================================================

    def _print_game_start(self) -> None:
        info = self.engine.get_game_info()
        print("=" * 60)
        print(f"游戏开始 | 精牌: {info['main_jin']}")
        for p in info['players']:
            if p['index'] in self.ai_players:
                ai_name = self.ai_players[p['index']].__class__.__name__
                ai_type = f"AI({ai_name})"
            else:
                ai_type = "人类"
            print(f"  Player{p['index']} {p['name']}: {ai_type}")
        print("=" * 60)

    def _print_zha_actions(self, actions: List[PlayerAction]) -> None:
        for a in actions:
            player = self.engine.players[a.source_player]
            print(f"  [扎牌] {player.name}: {a.description}")

    def _print_round_result(self, result: RoundResult) -> None:
        if result.win_type.value == "huang":
            print(f"\n--- 流局 ---")
        else:
            winner = self.engine.players[result.winner]
            mo = "自摸" if result.is_zi_mo else "捉统"
            print(f"\n--- {winner.name} {mo}！{result.total_hu}胡 = {result.total_score}分 ---")

    def get_game_log(self) -> GameLog:
        return self.game_log

    def stop(self) -> None:
        """停止游戏"""
        self._stop_flag = True
