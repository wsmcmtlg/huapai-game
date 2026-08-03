"""
花牌应用主类
=============
整合 pygame 主循环、场景管理、本地桥接通信层。
支持本地对战模式（AI 对手）和 WebSocket 在线对战模式。

修改说明：
- 本地模式使用 LocalBridge（同步 + 事件队列），不再依赖 asyncio
- game_state 事件通过 GameStateManager.snapshot 驱动 TableRenderer
- 精牌信息、出牌通知等事件直接更新 UI 组件
- 移除对 clear_hud() 的依赖（GameScene 未定义该方法）
- 修复 on_discard_card 使用 HumanInputGate.set_result_by_card_id
"""

from __future__ import annotations

import logging
import sys
import os
import time

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CLIENT_WS_PATH = os.path.join(_PROJECT_ROOT, "客户端 WebSocket")
_LOCAL_BRIDGE_PATH = os.path.join(_PROJECT_ROOT, "本地桥接")

for p in [_PROJECT_ROOT, _CLIENT_WS_PATH, _LOCAL_BRIDGE_PATH]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

from ui.constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, FPS, WINDOW_TITLE, Colors,
)
from ui.screens.scene_base import SceneManager, SceneType
from ui.screens.scene_lobby import LobbyScene
from ui.screens.scene_game import GameScene
from ui.utils.font_manager import init_pygame_font

logger = logging.getLogger(__name__)


class HuaPaiApp:
    """花牌应用主类

    Usage:
        app = HuaPaiApp()
        app.run()

        # 本地对战模式
        app = HuaPaiApp(local_mode=True)
        app.run()
    """

    def __init__(self, headless: bool = False, local_mode: bool = False):
        self._headless = headless
        self._running = False
        self._local_mode = local_mode
        self._client = None
        self._bridge = None

        self._screen = None
        self._clock = None

        self._scene_manager = SceneManager()

        self._lobby = LobbyScene(app=self)
        self._game = GameScene(app=self)

        self._scene_manager.register(SceneType.LOBBY, self._lobby)
        self._scene_manager.register(SceneType.GAME, self._game)

        self._game.set_callbacks(
            on_discard=self.on_discard_card,
            on_respond=self.on_respond_action,
            on_back=self.on_leave_room,
            on_send_chat=lambda msg: self._do_send_chat(msg),
        )

        self._scene_manager.switch_to(SceneType.LOBBY)

        if local_mode:
            self._init_local_mode()

    # ================================================================
    # 本地对战模式
    # ================================================================

    def _init_local_mode(self) -> None:
        """初始化本地对战模式"""
        try:
            from local_bridge import LocalBridge
            self._bridge = LocalBridge(
                human_seat=0,
                ai_config={1: "medium", 2: "simple"},
                action_timeout=120.0,
            )
            self._setup_local_callbacks()
            logger.info("本地对战模式已启用")
        except ImportError as e:
            logger.error("无法导入 LocalBridge: %s", e)
            self._local_mode = False

    def _setup_local_callbacks(self) -> None:
        """设置本地桥接模式的事件回调

        事件流：
        游戏线程 → LocalBridge._emit() → 事件队列 → update() → _fire_callbacks() → UI 更新
        """
        if not self._bridge:
            return

        bridge = self._bridge

        # ------ 连接状态 ------
        bridge.on("connected", lambda mt, d: (
            self._lobby.update_connection_state(True),
            self._lobby.add_system_message("本地对战模式已就绪"),
        ))

        bridge.on("disconnected", lambda mt, d: (
            self._lobby.update_connection_state(False),
            self._lobby.add_system_message("已断开连接"),
        ))

        # ------ 加入房间 ------
        bridge.on("joined", lambda mt, d: (
            self._lobby.update_room_state(True),
            self._lobby.add_system_message(f"已加入房间 {d.get('room_id', '')}"),
        ))

        # ------ 玩家列表 ------
        def on_player_list(mt, data):
            players = data.get("players", [])
            self._lobby.update_player_list(players)
        bridge.on("player_list", on_player_list)

        # ------ 游戏开始 ------
        def on_game_start(mt, d):
            self._scene_manager.switch_to(SceneType.GAME)
            self._game.add_system_message("游戏开始！")
            # 清理上一局的出牌区
            self._game._table.clear_discard_pile()
            self._game._table._discard_pile.clear()
            self._game.hide_action_panel()
        bridge.on("game_start", on_game_start)

        # ------ 游戏状态更新（核心：驱动 TableRenderer） ------
        def on_game_state(mt, data):
            if self._bridge and hasattr(self._bridge, '_state_manager'):
                sm = self._bridge._state_manager
                self._game._table.update_from_state(sm)
        bridge.on("game_state", on_game_state)

        # ------ 操作通知（某人执行了操作） ------
        def on_action_notify(mt, data):
            desc = data.get("description", "")
            player_index = data.get("player_index", -1)

            if desc:
                self._game.add_info_message(desc)

            self._game.hide_action_panel()

            # 如果是出牌，添加到出牌区
            cards = data.get("cards", [])
            action_type = data.get("action_type", "")
            if cards and action_type == "过" and player_index >= 0:
                # 这是出牌通知（我们用 PASS + cards 表示出牌）
                card_data = cards[0]
                self._game.add_discard(card_data, player_index)

            # 更新渲染状态（melds 等可能变化）
            if self._bridge and hasattr(self._bridge, '_state_manager'):
                sm = self._bridge._state_manager
                self._game._table.update_from_state(sm)
        bridge.on("action_notify", on_action_notify)

        # ------ 人类需要操作 ------
        def on_action_required(mt, data):
            available = data.get("available", [])
            actions = []
            for a in available:
                actions.append({
                    "action_type": a.get("action_type", a.get("type", "")),
                    "cards": a.get("cards", []),
                    "description": a.get("description", ""),
                })
            if actions:
                self._game.show_action_required(actions)
            text = data.get("description", "请操作")
            self._game.add_info_message(text, (100, 200, 255))
        bridge.on("action_required", on_action_required)

        # ------ 游戏结果 ------
        def on_game_result(mt, data):
            is_winner = False
            winners = data.get("winners", [])
            if isinstance(winners, list) and 0 in winners:
                is_winner = True

            result_data = {
                "win_type": data.get("win_type", ""),
                "total_hu": data.get("total_hu", 0),
                "total_score": data.get("total_score", 0),
                "main_jin": data.get("main_jin", ""),
            }

            def on_continue():
                # 继续下一局 — 当前游戏线程已结束，需要重新启动
                if self._bridge:
                    self._game._table.clear_discard_pile()
                    self._game._table._discard_pile.clear()
                    self._game.hide_result()
                    self._game.hide_action_panel()
                    self._bridge.start_local_game(name="我")

            def on_leave():
                if self._bridge:
                    self._bridge._running = False
                self._scene_manager.switch_to(SceneType.LOBBY)
                self._lobby.update_room_state(False)
                self._lobby.add_system_message("已离开房间")

            self._game.show_result(result_data, is_winner, on_continue, on_leave)
            self._game.add_system_message(
                f"{'你赢了' if is_winner else '本局结束'}！"
                f" {data.get('total_hu', 0)}胡={data.get('total_score', 0)}分"
            )
        bridge.on("game_result", on_game_result)

        # ------ 游戏结束 ------
        bridge.on("game_over", lambda mt, d: (
            self._lobby.add_system_message(
                f"游戏结束，共完成 {d.get('completed_rounds', 0)} 局"
            ),
            self._scene_manager.switch_to(SceneType.LOBBY),
            self._lobby.update_room_state(False),
        ))

        # ------ 信息消息 ------
        def on_info_message(mt, data):
            text = data.get("text", "")
            if text:
                self._game.add_info_message(text)
        bridge.on("info_message", on_info_message)

        # ------ 聊天消息 ------
        def on_chat_msg(mt, data):
            sender = data.get("sender", "未知")
            message = data.get("message", "")
            self._game.add_chat_message(sender, message)
            self._lobby.add_chat_message(sender, message)
        bridge.on("chat_msg", on_chat_msg)

        # ------ 错误 ------
        def on_error(mt, data):
            code = data.get("code", 9999)
            message = data.get("message", "未知错误")
            self._lobby.add_system_message(f"错误 [{code}]: {message}")
            self._game.add_system_message(f"错误: {message}", Colors.TEXT_RED)
        bridge.on("error", on_error)

    # ================================================================
    # 生命周期
    # ================================================================

    def run(self) -> None:
        if self._headless:
            logger.info("无头模式，不启动窗口")
            return

        import pygame
        pygame.init()
        init_pygame_font()

        self._screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption(WINDOW_TITLE)
        self._clock = pygame.time.Clock()

        self._running = True
        logger.info("应用启动: %s %dx%d", WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT)

        try:
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("用户中断")
        finally:
            self._shutdown()
            pygame.quit()

    def _main_loop(self) -> None:
        import pygame

        while self._running:
            dt = self._clock.tick(FPS) / 1000.0

            # 消费本地桥接的待处理事件（将游戏线程的事件转发到 UI）
            if self._bridge:
                self._bridge.update()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                    break

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                    current = self._scene_manager.current
                    if current and hasattr(current, "handle_right_click"):
                        current.handle_right_click(event.pos)

                else:
                    current = self._scene_manager.current
                    if current:
                        current.handle_event(event)

            current = self._scene_manager.current
            if current:
                current.update(dt)

            if self._screen:
                current = self._scene_manager.current
                if current:
                    current.render(self._screen)
                pygame.display.flip()

    def _shutdown(self) -> None:
        self._running = False
        if self._bridge:
            self._bridge._running = False

    # ================================================================
    # 客户端操作
    # ================================================================

    def _do_send_chat(self, msg: str) -> None:
        if self._bridge and self._local_mode:
            self._bridge._emit("chat_msg", {"sender": "我", "message": msg})
        elif self._client:
            pass  # WebSocket 模式暂不处理

    def on_join_room(self, room_id: str, name: str) -> None:
        if self._local_mode and self._bridge:
            self._lobby.add_system_message(f"本地模式：正在加入房间...")
            return

    def on_create_room(self, name: str) -> None:
        if self._local_mode and self._bridge:
            self._lobby.add_system_message("正在启动本地对战...")
            return

    def on_ready(self) -> None:
        if self._local_mode and self._bridge:
            return
        if self._client:
            pass

    def on_unready(self) -> None:
        pass

    def on_local_start(self) -> None:
        """开始本地对战（从大厅"本地对战"按钮触发）"""
        if self._bridge is None:
            self._init_local_mode()
            self._local_mode = True

        if self._bridge:
            name = "我"
            self._lobby.add_system_message("正在启动本地对战...")
            self._bridge.start_local_game(name=name)

    def on_leave_room(self) -> None:
        if self._bridge and self._local_mode:
            self._bridge._running = False
            self._scene_manager.switch_to(SceneType.LOBBY)
            self._lobby.update_room_state(False)
            self._lobby.add_system_message("已离开房间")
            return

    def on_discard_card(self, card_id: int) -> None:
        """出牌（由 GameScene 调用）

        通过 HumanInputGate 将 card_id 转换为 Card 对象，
        设置为人类输入结果。
        """
        if self._bridge and self._local_mode:
            success = self._bridge._gate.set_result_by_card_id(
                card_id, self._bridge._human_seat, self._bridge._controller
            )
            if success:
                self._game.hide_action_panel()
            else:
                logger.warning("出牌失败: card_id=%d, gate_waiting=%s, context=%s",
                               card_id, self._bridge._gate.is_waiting, self._bridge._gate.context)
            return

    def on_respond_action(self, action_type: str) -> None:
        """响应操作（由 GameScene 调用）

        action_type: "hu" / "zhao" / "pen" / "chow" / "pass" 等
        """
        if self._bridge and self._local_mode:
            self._bridge._gate.set_result(action_type)
            self._game.hide_action_panel()
            return
