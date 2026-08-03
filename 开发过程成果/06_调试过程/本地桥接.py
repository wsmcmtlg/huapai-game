"""
本地桥接 — 进程内游戏模拟（简化版）
========================================
在同一进程中运行 AIGameController + 人类玩家 UI，
绕过 WebSocket 和异步事件循环，通过同步回调桥接。

架构：
    pygame 主线程 (UI)
        ↕ 同步回调 + 事件队列
    游戏线程 (AIGameController + AI决策)
        ↕ HumanInputGate 门控
    人类玩家操作 (UI → set_result)

关键改进（相比原版）：
- 不再依赖 asyncio，消除线程安全问题
- 直接使用 AIGameController 的同步游戏循环
- 通过事件队列实现跨线程通信
- 通过 GameStateManager 实时跟踪游戏状态驱动 UI 渲染

用法：
    bridge = LocalBridge(human_seat=0, ai_config={1: "medium", 2: "simple"})
    bridge.start_local_game()
    # 在 pygame 主循环中调用 bridge.update()
"""

from __future__ import annotations

import logging
import sys
import os
import time
import threading
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import IntEnum

logger = logging.getLogger(__name__)

# 路径设置 — 确保能 import engine, ai 等模块
_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
_PHASE1_PATH = os.path.join(_PROJECT_ROOT, "Phase 1 规则引擎")
_AI_PATH = os.path.join(_PROJECT_ROOT, "AI")

for _p in [_PROJECT_ROOT, _PHASE1_PATH, _AI_PATH]:
    _abs = os.path.abspath(_p)
    if os.path.exists(_abs) and _abs not in sys.path:
        sys.path.insert(0, _abs)


# ============================================================
# 事件类型枚举
# ============================================================

class _EVT(IntEnum):
    """内部事件类型编码（避免依赖 pygame 自定义事件）"""
    INFO_MESSAGE   = 0   # 信息提示
    GAME_START     = 1   # 游戏开始
    GAME_STATE     = 2   # 游戏状态更新
    ACTION_NOTIFY  = 3   # 操作通知（某人执行了某操作）
    GAME_RESULT    = 4   # 本局结果
    GAME_OVER      = 5   # 整场游戏结束
    DISCARD_NOTIFY = 6   # 出牌通知
    ACTION_REQUIRED= 7   # 人类需要操作


# ============================================================
# GameStateManager — 跟踪游戏状态供 UI 查询
# ============================================================

class GameStateManager:
    """游戏状态管理器

    维护一份供 UI 渲染层查询的实时游戏状态快照。
    在游戏循环的每个关键节点更新。
    """

    def __init__(self):
        self.round_num: int = 0
        self.state: str = "IDLE"
        self.current_player: int = -1
        self.dealer: int = 0
        self.pool_remaining: int = 0
        self.main_jin: str = ""
        self.vice_jin: str = ""
        self.action_timeout: float = 120.0
        self.has_pending_action: bool = False

        self._self_player: Optional[_PlayerState] = None
        self._other_players: List[_PlayerState] = []
        self._pending_actions: List[Dict[str, Any]] = []

    def update_from_engine(self, engine) -> None:
        """从 GameEngine 更新状态"""
        info = engine.get_game_info()
        self.round_num = info["round_num"]
        self.state = info["state"]
        self.current_player = info["current_player"]
        self.dealer = info["dealer"]
        self.pool_remaining = info["pool_remaining"]
        self.main_jin = info["main_jin"] or ""
        self.vice_jin = info["vice_jin"] or ""

        self._other_players.clear()
        for p_info in info["players"]:
            pid = p_info["index"]
            player = engine.players[pid]

            if pid == 0:  # 人类玩家（座位0）
                self._self_player = _PlayerState(
                    index=player.index,
                    name=player.name,
                    hand=list(player.hand),
                    hand_count=player.hand_size,
                    melds=list(player.melds),
                    is_dealer=player.is_dealer,
                )
            else:
                self._other_players.append(_PlayerState(
                    index=player.index,
                    name=player.name,
                    hand_count=player.hand_size,
                    melds=list(player.melds),
                    is_dealer=player.is_dealer,
                ))

    @property
    def self_player(self) -> Optional[_PlayerState]:
        return self._self_player

    @property
    def other_players(self) -> List[_PlayerState]:
        return self._other_players

    @property
    def snapshot(self) -> "_GameSnapshot":
        return _GameSnapshot(self)


@dataclass
class _PlayerState:
    """玩家状态数据"""
    index: int
    name: str
    hand: List[Any] = field(default_factory=list)
    hand_count: int = 0
    melds: List[Any] = field(default_factory=list)
    is_dealer: bool = False


class _GameSnapshot:
    """游戏快照（供 TableRenderer.update_from_state 使用）

    TableRenderer 会读取 snapshot.round_num, snapshot.current_player,
    snapshot.pool_remaining, snapshot.self_player, snapshot.other_players
    """

    def __init__(self, state_manager: GameStateManager):
        self.round_num = state_manager.round_num
        self.current_player = state_manager.current_player
        self.pool_remaining = state_manager.pool_remaining
        self.self_player = state_manager._self_player
        self.other_players = state_manager._other_players


# ============================================================
# HumanInputGate — 人类玩家输入门控
# ============================================================

class HumanInputGate:
    """人类玩家输入门控

    在游戏循环中需要人类操作时，游戏线程等待，
    UI 线程通过 set_result() 提交结果。
    """

    def __init__(self):
        self._result: Optional[Any] = None
        self._waiting: bool = False
        self._context: str = ""          # "discard" / "response" / "zha" / "self_check"
        self._available_actions: List[Any] = []

    def wait_for_input(self, context: str, available: List[Any] = None) -> None:
        """开始等待人类输入（游戏线程调用）"""
        self._waiting = True
        self._context = context
        self._available_actions = available or []
        self._result = None

    def set_result(self, result: Any) -> None:
        """设置人类输入结果（UI 线程调用）"""
        if self._waiting:
            self._result = result
            self._waiting = False

    def set_result_by_card_id(self, card_id: int, player_index: int, controller=None) -> bool:
        """通过 card_id 设置出牌结果（UI 线程调用）

        从 controller.engine.players[player_index].hand 中查找对应卡牌，
        然后调用 set_result(card)。

        Args:
            card_id: 牌的 ID
            player_index: 玩家索引
            controller: AIGameController 实例（用于访问 engine）

        Returns:
            是否成功找到牌并设置结果
        """
        if not self._waiting or self._context != "discard":
            return False
        if controller is None:
            logger.warning("set_result_by_card_id: controller 为 None")
            return False

        player = controller.engine.players[player_index]
        for card in player.hand:
            if card.id == card_id:
                self.set_result(card)
                return True

        logger.warning("set_result_by_card_id: 未找到 card_id=%d", card_id)
        return False

    @property
    def is_waiting(self) -> bool:
        return self._waiting

    @property
    def is_ready(self) -> bool:
        return self._result is not None

    @property
    def result(self) -> Any:
        return self._result

    @property
    def context(self) -> str:
        return self._context

    @property
    def available_actions(self) -> List[Any]:
        return self._available_actions

    def reset(self) -> None:
        self._result = None
        self._waiting = False
        self._context = ""
        self._available_actions.clear()

    def poll(self, timeout: float = 0.05) -> bool:
        """轮询检查结果是否就绪（游戏线程调用）

        Args:
            timeout: 单次等待时间（秒）

        Returns:
            是否已收到结果
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_ready:
                return True
            time.sleep(0.01)
        return self.is_ready

    def wait(self, timeout: float = 120.0) -> Any:
        """阻塞等待结果（游戏线程调用）

        Args:
            timeout: 最长等待时间（秒）

        Returns:
            人类输入的结果，超时返回 None
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_ready:
                return self._result
            time.sleep(0.02)
        logger.warning("HumanInputGate 等待超时 (%.1f秒), context=%s", timeout, self._context)
        return None


# ============================================================
# LocalBridge — 本地桥接主类
# ============================================================

class LocalBridge:
    """本地桥接

    替代 WebSocket 通信，在进程内直接运行 AIGameController。
    人类玩家占座位 0（下方），AI 占座位 1 和 2。
    """

    def __init__(
        self,
        human_seat: int = 0,
        ai_config: Optional[Dict[int, str]] = None,
        action_timeout: float = 120.0,
        seed: Optional[int] = None,
    ):
        self._human_seat = human_seat
        self._ai_config = ai_config or {1: "medium", 2: "simple"}
        self._action_timeout = action_timeout
        self._seed = seed

        self._callbacks: Dict[str, List[Callable]] = {}
        self._state_manager = GameStateManager()
        self._gate = HumanInputGate()
        self._controller = None
        self._game_thread: Optional[threading.Thread] = None
        self._running = False
        self._connected = False
        self._event_queue: List[tuple] = []
        self._event_lock = threading.Lock()
        self._player_name = "我"

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def state(self) -> GameStateManager:
        return self._state_manager

    # ================================================================
    # 事件回调
    # ================================================================

    def on(self, event: str, callback: Callable) -> None:
        """注册事件回调"""
        self._callbacks.setdefault(event, []).append(callback)

    def _emit(self, event: str, data: Dict[str, Any]) -> None:
        """触发事件回调（UI 线程安全：在 update() 中执行）"""
        self._event_queue.append((event, data))

    def _fire_callbacks(self, event: str, data: Dict[str, Any]) -> None:
        """实际执行回调（必须在 UI 线程中调用）"""
        for cb in self._callbacks.get(event, []):
            try:
                cb(event, data)
            except Exception as e:
                logger.error("事件回调异常: event=%s, error=%s", event, e, exc_info=True)

    # ================================================================
    # UI 主线程调用 — update()
    # ================================================================

    def update(self) -> None:
        """消费待处理事件（由 pygame 主循环每帧调用）"""
        with self._event_lock:
            events = list(self._event_queue)
            self._event_queue.clear()

        for event_name, data in events:
            self._fire_callbacks(event_name, data)

    # ================================================================
    # 异步接口兼容（供 app.py 调用）
    # ================================================================

    async def connect(self) -> None:
        self._connected = True
        self._emit("connected", {"player_id": "local_human"})

    async def disconnect(self) -> None:
        self._running = False
        self._connected = False
        self._emit("disconnected", {"reconnect_count": 0})

    async def join_room(self, room_id: str, name: str = "") -> bool:
        self._player_name = name or "我"
        self._join_room_sync(name)
        return True

    async def ready(self) -> bool:
        self._ready_sync()
        return True

    async def leave_room(self) -> bool:
        self._running = False
        if self._game_thread and self._game_thread.is_alive():
            self._game_thread.join(timeout=3)
        self._controller = None
        self._emit("left", {"player_id": "local_human", "name": self._player_name})
        return True

    async def unready(self) -> bool:
        return True

    async def discard(self, card_id: int) -> bool:
        return self._gate.set_result_by_card_id(
            card_id, self._human_seat, self._controller
        )

    async def respond(self, action_type: str) -> bool:
        if self._gate.is_waiting and self._gate.context in ("response", "zha", "self_check"):
            self._gate.set_result(action_type)
            return True
        return False

    async def send_chat(self, message: str) -> bool:
        self._emit("chat_msg", {"sender": self._player_name, "message": message})
        return True

    # ================================================================
    # 同步启动（供 app.py 直接调用）
    # ================================================================

    def start_local_game(self, name: str = "我") -> None:
        """一站式启动本地游戏（同步）"""
        self._player_name = name
        self._connected = True
        self._emit("connected", {"player_id": "local_human"})
        self._join_room_sync(name)
        self._ready_sync()

    def _join_room_sync(self, name: str) -> None:
        """同步加入房间：创建 AIGameController"""
        self._player_name = name

        from ai.controller import AIGameController

        self._controller = AIGameController(
            ai_config=self._ai_config,
            player_names=["我", "AI-中等", "AI-简单"],
            seed=self._seed,
            verbose=True,
        )
        # 注册人类输入回调
        self._controller.on_human_input = self._on_human_input_needed

        self._emit("joined", {
            "room_id": "local_room",
            "seat": self._human_seat,
            "name": self._player_name,
        })
        self._emit("player_list", {
            "room_id": "local_room",
            "players": [
                {"player_id": "local_human", "name": "我", "seat": 0, "is_ready": True, "is_ai": False},
                {"player_id": "ai_1", "name": "AI-中等", "seat": 1, "is_ready": True, "is_ai": True},
                {"player_id": "ai_2", "name": "AI-简单", "seat": 2, "is_ready": True, "is_ai": True},
            ],
            "count": 3,
        })

    def _ready_sync(self) -> None:
        """同步准备：启动游戏线程"""
        if self._controller is None:
            return
        self._running = True
        self._game_thread = threading.Thread(target=self._run_game_loop, daemon=True)
        self._game_thread.start()

    # ================================================================
    # 游戏循环（在独立线程中运行）
    # ================================================================

    def _run_game_loop(self) -> None:
        """游戏主循环（游戏线程）"""
        try:
            self._emit("info_message", {"text": "游戏初始化中..."})
            self._emit("game_start", {"max_rounds": 10})

            self._patch_controller_hooks()
            result_log = self._controller.run_game(max_rounds=10)

            self._emit("game_over", {"completed_rounds": len(result_log.round_results)})

        except Exception as e:
            logger.error("游戏循环异常: %s", e, exc_info=True)
            self._emit("info_message", {"text": f"游戏异常: {e}"})
        finally:
            self._running = False

    def _patch_controller_hooks(self) -> None:
        """给 GameEngine 注入回调钩子，将状态变化转发到事件队列"""
        engine = self._controller.engine

        def on_state_change(state, info):
            self._state_manager.update_from_engine(engine)
            self._emit("game_state", info)

        def on_action(action):
            from core.actions import ActionPriority
            type_name_map = {
                ActionPriority.PASS: "过", ActionPriority.CHOW: "吃",
                ActionPriority.PEN: "对", ActionPriority.ZHAO: "招",
                ActionPriority.CHUAN: "穿", ActionPriority.ZHA: "扎",
                ActionPriority.FAN: "泛", ActionPriority.HU: "胡",
            }
            action_type_name = type_name_map.get(action.action_type, "?")
            player = engine.players[action.source_player]
            desc = f"{player.name}: {action.description}"

            self._emit("action_notify", {
                "action_type": action_type_name,
                "description": desc,
                "player_index": action.source_player,
                "cards": [{"id": c.id, "char": c.char, "color": c.color,
                           "char_type": c.char_type}
                          for c in action.cards],
            })

            # 如果有人出牌，额外发送出牌通知
            if action.action_type == ActionPriority.PASS:
                # pass 不需要特殊通知
                pass
            else:
                # 更新状态以便 UI 刷新 melds
                self._state_manager.update_from_engine(engine)
                self._emit("game_state", engine.get_game_info())

        def on_round_end(result):
            self._emit("game_result", {
                "winner": result.winner,
                "winners": result.winners,
                "total_hu": result.total_hu,
                "total_score": result.total_score,
                "is_zi_mo": result.is_zi_mo,
                "win_type": result.win_type.value if hasattr(result.win_type, "value") else str(result.win_type),
                "main_jin": result.main_jin,
                "remaining_cards": result.remaining_cards,
                "round_num": result.round_num,
                "loser": result.loser,
            })

        engine.on_state_change = on_state_change
        engine.on_action = on_action
        engine.on_round_end = on_round_end

    def _on_human_input_needed(self, input_type: str, context: Dict[str, Any] = None) -> Any:
        """人类输入回调（游戏线程中调用）

        通过门控暂停游戏循环，等待 UI 线程提交操作。

        Args:
            input_type: 输入类型 "discard" / "response" / "zha" / "self_check"
            context: 上下文信息，包含 "available"（可执行操作列表）等

        Returns:
            人类输入的结果（Card / PlayerAction / str 等）
        """
        context = context or {}
        self._gate.wait_for_input(input_type, context.get("available", []))

        # 通知 UI 需要操作
        if input_type == "discard":
            self._emit("info_message", {"text": "轮到你出牌"})
            self._state_manager.has_pending_action = True
            self._emit("action_required", {
                "description": "请选择要打出的牌",
                "available": [],
            })

        elif input_type == "response":
            actions = context.get("available", [])
            action_dicts = []
            for a in actions:
                from core.actions import ActionPriority
                type_name_map = {
                    ActionPriority.HU: "hu", ActionPriority.CHUAN: "chuan",
                    ActionPriority.ZHAO: "zhao", ActionPriority.PEN: "pen",
                    ActionPriority.CHOW: "chow", ActionPriority.PASS: "pass",
                }
                action_dicts.append({
                    "action_type": type_name_map.get(a.action_type, "pass"),
                    "cards": [{"id": c.id, "char": c.char, "color": c.color,
                               "char_type": c.char_type}
                              for c in a.cards],
                    "description": a.description,
                })
            self._state_manager.has_pending_action = True
            self._emit("action_required", {
                "description": "请选择操作",
                "available": action_dicts,
            })

        elif input_type == "zha":
            zha_list = context.get("available", [])
            zha_dicts = []
            for a in zha_list:
                zha_dicts.append({
                    "action_type": "zha",
                    "cards": [{"id": c.id, "char": c.char} for c in a.cards],
                    "description": a.description,
                })
            self._state_manager.has_pending_action = True
            self._emit("action_required", {
                "description": "是否扎牌？",
                "available": zha_dicts,
            })

        elif input_type == "self_check":
            actions = context.get("available", [])
            action_dicts = []
            for a in actions:
                from core.actions import ActionPriority
                type_name_map = {
                    ActionPriority.HU: "hu", ActionPriority.CHUAN: "chuan",
                    ActionPriority.ZHAO: "zhao", ActionPriority.PEN: "pen",
                    ActionPriority.CHOW: "chow", ActionPriority.ZHA: "zha",
                    ActionPriority.FAN: "fan", ActionPriority.PASS: "pass",
                }
                action_dicts.append({
                    "action_type": type_name_map.get(a.action_type, "pass"),
                    "cards": [{"id": c.id, "char": c.char, "color": c.color,
                               "char_type": c.char_type}
                              for c in a.cards],
                    "description": a.description,
                })
            self._state_manager.has_pending_action = True
            self._emit("action_required", {
                "description": "请选择操作（自摸检查）",
                "available": action_dicts,
            })

        # 阻塞等待 UI 线程提交结果
        result = self._gate.wait(timeout=self._action_timeout)

        # 操作完成后重置状态
        self._state_manager.has_pending_action = False
        self._emit("game_state", self._controller.engine.get_game_info())

        return result
