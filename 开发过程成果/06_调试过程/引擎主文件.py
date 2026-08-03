"""
core/engine.py — 花牌游戏引擎主控
=================================
管理游戏完整生命周期：初始化 → 发牌 → 反向扎牌 → 打牌 → 结算。

协调 Card/Deck、Player、ActionValidator、HandAnalyzer、ScoreCalculator 各模块。

3人游戏核心设定：
- 22种字面 × 5张 = 110张 + 2张赖子 = 112张
- 庄家26张，旁家25张，发牌后余36张
- 反向扎牌阶段：上家(2) → 下家(1) → 庄家(0)
- 座位顺序：庄家(0) → 下家(1) → 上家(2)
- 精牌翻牌确定：从三/五/七中选一个作为主精

游戏阶段状态机：
  IDLE → DEALING → ZHA_PHASE → DEALER_CHECK_HU → DEALER_DISCARD
  → PLAYER_RESPONSE → DRAW_CARD → SELF_CHECK → PLAYER_DISCARD
  → PEN_DISCARD → GAME_OVER → SETTLE
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional, Tuple

from .card import Card, Deck
from .melds import (
    DEALER_HAND_COUNT, INIT_HAND_COUNT, PLAYER_COUNT,
    GamePhase, MeldType, WinType, Direction,
    RED_JING_CHARS, WILD_USABLE_CHARS, WILD_CHAR,
    TOTAL_CARD_COUNT,
)
from .player import Player
from .actions import ActionValidator, ActionPriority, PlayerAction
from .analyzer import HandAnalyzer, AnalysisResult
from .scoring import ScoreCalculator, Meld
from .rules import GameRules, DEFAULT_RULES


class EngineState(Enum):
    """引擎状态（与GamePhase对应）"""
    IDLE             = auto()  # 空闲，等待开始
    DEALING          = auto()  # 发牌
    ZHA_PHASE        = auto()  # 反向扎牌阶段
    DEALER_CHECK_HU  = auto()  # 庄家天胡判定
    DEALER_DISCARD   = auto()  # 庄家出牌
    WAITING_RESPONSE = auto()  # 等待旁家响应（胡/招/对/吃）
    DRAW_CARD        = auto()  # 玩家摸牌
    SELF_CHECK       = auto()  # 自摸后检查（胡/扎/穿）
    PLAYER_DISCARD   = auto()  # 当前玩家出牌
    PEN_DISCARD      = auto()  # 对牌后出牌
    GAME_OVER        = auto()  # 本局结束
    SETTLE           = auto()  # 结算


@dataclass
class RoundResult:
    """本局结果"""
    winner: Optional[int] = None              # 赢家索引
    winners: List[int] = field(default_factory=list)  # 赢家列表
    total_hu: int = 0                          # 总胡数
    total_score: int = 0                       # 总得分
    is_zi_mo: bool = False                     # 是否自摸
    win_type: WinType = WinType.HUANG_ZHUANG   # 胡牌方式
    main_jin: Optional[str] = None             # 主精字面
    melds_detail: List[Meld] = field(default_factory=list)  # 牌型明细
    remaining_cards: int = 0                   # 余牌数
    round_num: int = 0                         # 局数
    loser: Optional[int] = None                # 输家索引（放炮者）

    def __repr__(self) -> str:
        if self.win_type == WinType.HUANG_ZHUANG:
            return f"RoundResult(黄庄, round={self.round_num})"
        winner_name = f"Player{self.winner}" if self.winner else "?"
        mo = "自摸" if self.is_zi_mo else "捉统"
        return (
            f"RoundResult({winner_name} {mo}, "
            f"{self.total_hu}胡={self.total_score}分, "
            f"type={self.win_type.value})"
        )


class GameEngine:
    """花牌游戏引擎主控

    管理完整的游戏生命周期，协调各子系统。
    """

    def __init__(
        self,
        player_names: Optional[List[str]] = None,
        rules: Optional[GameRules] = None,
    ):
        """初始化游戏引擎

        Args:
            player_names: 3个玩家的名称列表
            rules: 游戏规则配置（None使用默认规则）
        """
        self.rules = rules or DEFAULT_RULES
        self.validator = ActionValidator()

        # 玩家初始化
        self.players: List[Player] = []
        names = player_names or ["庄家", "下家", "上家"]
        for i, name in enumerate(names[:PLAYER_COUNT]):
            p = Player(index=i, name=name)
            if i == 0:
                p.is_dealer = True
            self.players.append(p)

        # 游戏状态
        self.state = EngineState.IDLE
        self.current_player: int = 0
        self.dealer: int = 0
        self.round_num: int = 0
        self.played_card: Optional[Card] = None
        self.last_played_by: int = -1
        self.discarded: List[Card] = []
        self.round_history: List[RoundResult] = []

        # 分析器和计分器（每局创建）
        self.analyzer: Optional[HandAnalyzer] = None
        self.calculator: Optional[ScoreCalculator] = None

        # 牌组
        self.deck: Optional[Deck] = None

        # 回调函数（用于UI/网络通信）
        self.on_state_change: Optional[Callable] = None
        self.on_action: Optional[Callable] = None
        self.on_round_end: Optional[Callable] = None

    # ==================== 游戏生命周期 ====================

    def start_game(self) -> None:
        """开始新游戏"""
        self.round_num = 0
        self.round_history.clear()
        self._start_new_round()

    def _start_new_round(self) -> None:
        """开始新一局"""
        self.round_num += 1
        self.state = EngineState.DEALING

        # 重置牌组和玩家
        self.deck = Deck()
        self.deck.shuffle()
        self.discarded.clear()
        self.played_card = None
        self.last_played_by = -1

        for player in self.players:
            player.reset_for_new_round()

        # 发牌：庄家26张，旁家各25张
        hands = self.deck.deal()
        for i, hand in enumerate(hands):
            self.players[i].set_hand(hand)

        # 确定精牌（默认先设为三，实际翻牌逻辑可覆盖）
        self._determine_jin_pai()

        # 设置分析器和计分器
        main_jin = self.deck.main_jin_char if self.deck else "三"
        self.analyzer = HandAnalyzer(rules=self.rules)
        self.calculator = ScoreCalculator(main_jin_char=main_jin)

        # 通知各玩家精牌信息
        for player in self.players:
            player.set_jin_pai(
                self.deck.main_jin_char,
                self.deck.vice_jin_char,
            )

        self._notify_state_change()

    def _determine_jin_pai(self) -> None:
        """从余牌池翻牌确定主精

        主精从三/五/七中选择（使胡数最大的字面）。
        此处实现简化版：从余牌池顶翻一张，
        如果是三/五/七之一则为主精，否则重新翻。
        """
        if not self.deck:
            return

        # 从余牌池中找到第一张三/五/七
        main_jin_candidates = list(WILD_USABLE_CHARS)
        for card in self.deck.cards:
            if card.char in main_jin_candidates:
                self.deck.set_main_jin(card)
                return

        # 找不到精牌时默认三
        from .melds import WILD_CHAR
        fallback = Card.create("三", card_id=-1)
        self.deck.set_main_jin(fallback)

    def finish_dealing(self) -> None:
        """发牌完成，进入反向扎牌阶段"""
        self.state = EngineState.ZHA_PHASE
        self._notify_state_change()

    # ==================== 反向扎牌阶段 ====================

    def zha_phase_players(self) -> List[int]:
        """反向扎牌阶段的出牌顺序：上家(2) → 下家(1) → 庄家(0)"""
        return [2, 1, 0]

    def process_zha_phase(self) -> List[PlayerAction]:
        """处理反向扎牌阶段

        依次检查上家、下家、庄家是否可扎牌。
        可扎牌的玩家执行扎牌并从余牌池底部补牌。

        Returns:
            所有执行的扎牌操作列表
        """
        executed_actions: List[PlayerAction] = []

        for player_idx in self.zha_phase_players():
            player = self.players[player_idx]
            zha_actions = self.validator.check_zha(player.hand, player_idx)

            for action in zha_actions:
                # 执行扎牌
                meld = Meld(
                    meld_type=MeldType.ZHA,
                    cards=tuple(action.cards),
                    is_open=False,
                )
                player.add_meld(meld)

                # 从余牌池底部补一张
                if self.deck:
                    card = self.deck.draw_bottom()
                    if card:
                        player.add_card(card)
                        player.last_drawn = card

                executed_actions.append(action)

        # 扎牌完成后，进入庄家天胡判定
        self.finish_dealing()
        return executed_actions

    # ==================== 庄家天胡判定 ====================

    def check_dealer_tian_hu(self) -> Optional[RoundResult]:
        """判定庄家天胡

        发牌+扎牌阶段后，庄家手牌+场上牌型总胡数>=17即可天胡。
        """
        if not self.analyzer:
            return None

        dealer = self.players[self.dealer]

        # 将手中牌和场上牌型合并分析
        all_cards = list(dealer.hand)
        for meld in dealer.melds:
            all_cards.extend(meld.cards)

        result = self.analyzer.analyze_hand(all_cards)
        if result and result.is_win:
            return self._settle_win(
                winner=self.dealer,
                is_zi_mo=True,
                win_type=WinType.TIAN_HU,
                melds=result.melds,
                total_hu=result.total_hu,
            )
        return None

    def start_dealer_discard(self) -> None:
        """庄家开始出牌（无人天胡时）"""
        self.state = EngineState.DEALER_DISCARD
        self.current_player = self.dealer
        self._notify_state_change()

    # ==================== 回合流转 ====================

    def get_current_player(self) -> Player:
        """获取当前出牌玩家"""
        return self.players[self.current_player]

    def next_player(self, from_player: int = -1) -> int:
        """下一个玩家（庄家0 → 下家1 → 上家2 → 庄家0）"""
        p = from_player if from_player >= 0 else self.current_player
        return (p + 1) % PLAYER_COUNT

    def previous_player(self, from_player: int = -1) -> int:
        """上一个玩家（庄家0 → 上家2 → 下家1 → 庄家0）"""
        p = from_player if from_player >= 0 else self.current_player
        return (p - 1) % PLAYER_COUNT

    def advance_turn(self) -> None:
        """推进到下一个玩家的回合"""
        self.current_player = self.next_player()
        self.state = EngineState.DRAW_CARD
        self._notify_state_change()

    def draw_card(self, player_index: int) -> Optional[Card]:
        """玩家从余牌池顶部摸牌

        Returns:
            摸到的牌，牌池为空时返回None
        """
        if not self.deck:
            return None
        card = self.deck.draw()
        if card:
            self.players[player_index].add_card(card)
            self.players[player_index].last_drawn = card
        return card

    # ==================== 出牌 ====================

    def play_card(self, player_index: int, card: Card) -> bool:
        """玩家出牌

        Args:
            player_index: 出牌玩家索引
            card: 要打出的牌

        Returns:
            是否成功出牌
        """
        player = self.players[player_index]

        # 检查牌是否在手牌中
        found = None
        for c in player.hand:
            if c.id == card.id:
                found = c
                break
        if found is None:
            return False

        player.remove_card(found)
        self.discarded.append(found)
        self.played_card = found
        self.last_played_by = player_index

        return True

    # ==================== 旁家响应判定 ====================

    def check_other_players_actions(
        self, played_card: Card, from_player: int,
    ) -> Dict[int, List[PlayerAction]]:
        """检查所有其他玩家对出牌的可执行操作

        Args:
            played_card: 被打出的牌
            from_player: 出牌的玩家索引

        Returns:
            {玩家索引: 可执行操作列表}
        """
        actions_by_player: Dict[int, List[PlayerAction]] = {}

        for i, player in enumerate(self.players):
            if i == from_player:
                continue

            # 判断是否为上家（影响吃牌权限）
            is_prev = (i == self.previous_player(from_player))

            actions = self.validator.get_available_actions(
                hand=player.hand,
                player_index=i,
                played_card=played_card,
                from_player=from_player,
                exposed_melds=player.get_exposed_melds(),
                is_previous_player=is_prev,
            )

            # 检查胡牌
            if self.analyzer:
                test_hand = list(player.hand) + [played_card]
                # 需要考虑场上已有牌型
                for meld in player.melds:
                    test_hand.extend(meld.cards)

                result = self.analyzer.analyze_hand(test_hand)
                if result and result.is_win:
                    actions.append(PlayerAction(
                        action_type=ActionPriority.HU,
                        cards=[played_card],
                        source_player=i,
                        target_player=from_player,
                        description=f"胡 {result.total_hu}胡",
                    ))

            if actions:
                actions_by_player[i] = actions

        return actions_by_player

    def resolve_actions(
        self, actions_by_player: Dict[int, List[PlayerAction]],
    ) -> Optional[PlayerAction]:
        """解决多玩家操作冲突，返回最终胜出的操作

        Args:
            actions_by_player: {玩家索引: 可执行操作列表}

        Returns:
            最终胜出的操作，None表示全部过
        """
        # 收集所有最高优先级操作
        all_actions: List[PlayerAction] = []
        for player_idx, player_actions in actions_by_player.items():
            all_actions.extend(player_actions)

        if not all_actions:
            return None

        # 按优先级排序
        all_actions.sort(key=lambda a: a.action_type, reverse=True)
        max_priority = all_actions[0].action_type

        # 获取所有最高优先级操作
        top_actions = [a for a in all_actions if a.action_type == max_priority]

        # 如果只有一个玩家有最高优先级操作
        players_with_top = set(a.source_player for a in top_actions)
        if len(players_with_top) == 1:
            return top_actions[0]

        # 多个玩家同优先级：按座位顺序（庄家 > 下家 > 上家）
        for idx in range(PLAYER_COUNT):
            for a in top_actions:
                if a.source_player == idx:
                    return a

        return top_actions[0]

    # ==================== 自摸检查 ====================

    def check_self_actions(self, player_index: int) -> List[PlayerAction]:
        """检查自摸时可执行的操作（扎/泛/胡）

        Args:
            player_index: 当前摸牌的玩家索引

        Returns:
            可执行操作列表
        """
        player = self.players[player_index]

        actions = self.validator.get_available_actions(
            hand=player.hand,
            player_index=player_index,
            check_self_draw=True,
        )

        # 检查自摸胡
        if self.analyzer:
            all_cards = list(player.hand)
            for meld in player.melds:
                all_cards.extend(meld.cards)

            result = self.analyzer.analyze_hand(all_cards)
            if result and result.is_win:
                actions.append(PlayerAction(
                    action_type=ActionPriority.HU,
                    cards=player.hand.copy(),
                    source_player=player_index,
                    description=f"自摸胡 {result.total_hu}胡",
                ))

        actions.sort(key=lambda a: a.action_type, reverse=True)
        return actions

    # ==================== 执行操作 ====================

    def execute_action(self, action: PlayerAction) -> Optional[RoundResult]:
        """执行玩家的操作

        Args:
            action: 要执行的操作

        Returns:
            如果是胡牌操作，返回RoundResult；否则None
        """
        player = self.players[action.source_player]

        if action.action_type == ActionPriority.HU:
            return self._execute_hu(action)
        elif action.action_type == ActionPriority.PEN:
            return self._execute_pen(player, action)
        elif action.action_type == ActionPriority.ZHAO:
            return self._execute_zhao(player, action)
        elif action.action_type == ActionPriority.CHUAN:
            return self._execute_chuan(player, action)
        elif action.action_type == ActionPriority.ZHA:
            return self._execute_zha(player, action)
        elif action.action_type == ActionPriority.FAN:
            return self._execute_fan(player, action)
        elif action.action_type == ActionPriority.CHOW:
            return self._execute_chow(player, action)

        return None

    def _execute_pen(self, player: Player, action: PlayerAction) -> None:
        """执行对牌（碰牌）

        从手中取2张 + 他人出的1张 = 3张明牌。
        对牌后当前玩家需要出一张牌。
        """
        meld = Meld(
            meld_type=MeldType.PEN,
            cards=tuple(action.cards),
            is_open=True,
            main_jin_char=player.main_jin_char,
        )
        player.add_meld(meld)

        # 对牌后出牌
        self.current_player = action.source_player
        self.state = EngineState.PEN_DISCARD
        self._notify_state_change()

    def _execute_zhao(self, player: Player, action: PlayerAction) -> None:
        """执行招牌（明杠）

        手中3张 + 他人出的1张 = 4张明牌。
        招牌后取余牌池顶部补一张，然后出牌。
        """
        meld = Meld(
            meld_type=MeldType.ZHAO,
            cards=tuple(action.cards),
            is_open=True,
            main_jin_char=player.main_jin_char,
        )
        player.add_meld(meld)

        # 取余牌池顶部补牌
        if self.deck:
            card = self.deck.draw()
            if card:
                player.add_card(card)
                player.last_drawn = card

        self.current_player = action.source_player
        self.state = EngineState.PLAYER_DISCARD
        self._notify_state_change()

    def _execute_chuan(self, player: Player, action: PlayerAction) -> None:
        """执行穿牌（5张明杠升级）

        已有扎牌(4张暗杠) + 他人出的1张 = 5张明牌。
        穿牌后取余牌池底部补一张。
        """
        meld = Meld(
            meld_type=MeldType.CHUAN,
            cards=tuple(action.cards),
            is_open=True,
            main_jin_char=player.main_jin_char,
        )
        # 注意：需要先从melds中移除原扎牌
        player.melds = [m for m in player.melds
                        if not (m.meld_type == MeldType.ZHA
                                and m.cards[0].char == action.cards[0].char)]
        player.add_meld(meld)

        # 取余牌池底部补牌
        if self.deck:
            card = self.deck.draw_bottom()
            if card:
                player.add_card(card)
                player.last_drawn = card

        self.current_player = action.source_player
        self.state = EngineState.PLAYER_DISCARD
        self._notify_state_change()

    def _execute_zha(self, player: Player, action: PlayerAction) -> None:
        """执行扎牌（暗杠，4张）

        手中4张同字面 = 4张暗牌。
        扎牌后取余牌池底部补一张。
        """
        meld = Meld(
            meld_type=MeldType.ZHA,
            cards=tuple(action.cards),
            is_open=False,
            main_jin_char=player.main_jin_char,
        )
        player.add_meld(meld)

        # 取余牌池底部补牌
        if self.deck:
            card = self.deck.draw_bottom()
            if card:
                player.add_card(card)
                player.last_drawn = card

        self.current_player = action.source_player
        self.state = EngineState.PLAYER_DISCARD
        self._notify_state_change()

    def _execute_fan(self, player: Player, action: PlayerAction) -> None:
        """执行泛牌（5张）

        手中5张同字面 = 5张。
        """
        meld = Meld(
            meld_type=MeldType.FAN,
            cards=tuple(action.cards),
            is_open=True,
            main_jin_char=player.main_jin_char,
        )
        player.add_meld(meld)

        # 泛牌后不需要补牌（手中已出完）
        self.current_player = action.source_player
        self.state = EngineState.PLAYER_DISCARD
        self._notify_state_change()

    def _execute_chow(self, player: Player, action: PlayerAction) -> None:
        """执行吃牌（顺子）

        手中2张 + 上家出的1张 = 3张顺子。
        吃牌后当前玩家需要出一张牌。
        """
        meld = Meld(
            meld_type=MeldType.SEQUENCE,
            cards=tuple(action.cards),
            is_open=True,
        )
        player.add_meld(meld)

        # 吃牌后出牌
        self.current_player = action.source_player
        self.state = EngineState.PLAYER_DISCARD
        self._notify_state_change()

    # ==================== 胡牌结算 ====================

    def _execute_hu(self, action: PlayerAction) -> RoundResult:
        """执行胡牌结算

        Args:
            action: 胡牌操作

        Returns:
            本局结算结果
        """
        player = self.players[action.source_player]
        is_zi_mo = (self.last_played_by == -1 or
                    self.last_played_by == action.source_player)

        if is_zi_mo:
            win_type = WinType.ZI_MO
            # 地胡判定：第一轮出牌后旁家即胡
            if (self.round_num == 1 and
                    self.state == EngineState.WAITING_RESPONSE and
                    not action.source_player == self.dealer):
                win_type = WinType.DI_HU
        else:
            win_type = WinType.ZHUO_TONG

        # 分析手牌
        all_cards = list(player.hand)
        for meld in player.melds:
            all_cards.extend(meld.cards)

        result = None
        total_hu = 0
        melds_detail = []

        if self.analyzer:
            result = self.analyzer.analyze_hand(all_cards)
            if result:
                total_hu = result.total_hu
                melds_detail = result.melds

        # 优化主精选择
        if melds_detail and self.calculator:
            best_jin = ScoreCalculator.find_best_main_jin(melds_detail)
            if best_jin:
                optimized_calc = ScoreCalculator(main_jin_char=best_jin)
                total_hu = optimized_calc.calculate_hand_hu(melds_detail)

        return self._settle_win(
            winner=action.source_player,
            is_zi_mo=is_zi_mo,
            win_type=win_type,
            melds=melds_detail,
            total_hu=total_hu,
            loser=None if is_zi_mo else self.last_played_by,
        )

    def _settle_win(
        self,
        winner: int,
        is_zi_mo: bool,
        win_type: WinType,
        melds: List[Meld],
        total_hu: int,
        loser: Optional[int] = None,
    ) -> RoundResult:
        """结算胡牌

        Args:
            winner: 赢家索引
            is_zi_mo: 是否自摸
            win_type: 胡牌方式
            melds: 牌型明细
            total_hu: 总胡数
            loser: 放炮者索引（自摸时为None）
        """
        total_score = self.rules.calc_total_score(total_hu)
        main_jin = self.deck.main_jin_char if self.deck else None

        round_result = RoundResult(
            winner=winner,
            winners=[winner],
            total_hu=total_hu,
            total_score=total_score,
            is_zi_mo=is_zi_mo,
            win_type=win_type,
            main_jin=main_jin,
            melds_detail=melds,
            remaining_cards=self.deck.remaining() if self.deck else 0,
            round_num=self.round_num,
            loser=loser,
        )
        self.round_history.append(round_result)
        self.state = EngineState.GAME_OVER
        self._notify_round_end(round_result)
        return round_result

    # ==================== 流局判定 ====================

    def check_liuju(self) -> bool:
        """检查是否流局（余牌池为空）"""
        return self.deck is None or self.deck.remaining() == 0

    def handle_liuju(self) -> RoundResult:
        """处理流局（黄庄）"""
        result = RoundResult(
            win_type=WinType.HUANG_ZHUANG,
            remaining_cards=0,
            round_num=self.round_num,
        )
        self.round_history.append(result)
        self.state = EngineState.GAME_OVER
        self._notify_round_end(result)
        return result

    # ==================== 游戏信息 ====================

    def get_game_info(self) -> Dict:
        """获取当前游戏状态摘要"""
        return {
            "round_num": self.round_num,
            "state": self.state.name,
            "current_player": self.current_player,
            "dealer": self.dealer,
            "pool_remaining": self.deck.remaining() if self.deck else 0,
            "main_jin": self.deck.main_jin_char if self.deck else None,
            "vice_jin": self.deck.vice_jin_char if self.deck else None,
            "players": [
                {
                    "index": p.index,
                    "name": p.name,
                    "direction": p.direction.name,
                    "hand_count": p.hand_size,
                    "meld_count": len(p.melds),
                    "is_dealer": p.is_dealer,
                }
                for p in self.players
            ],
            "discarded_count": len(self.discarded),
            "history_count": len(self.round_history),
        }

    def get_player_hand(self, player_index: int) -> List[Card]:
        """获取指定玩家的手牌副本"""
        return self.players[player_index].hand.copy()

    def set_dealer(self, player_index: int) -> None:
        """设置庄家"""
        for p in self.players:
            p.is_dealer = False
        self.players[player_index].is_dealer = True
        self.dealer = player_index

    def rotate_dealer(self) -> int:
        """轮换庄家（下一家做庄）

        Returns:
            新庄家索引
        """
        self.set_dealer(self.next_player(self.dealer))
        return self.dealer

    # ==================== 回调通知 ====================

    def _notify_state_change(self) -> None:
        """通知状态变更"""
        if self.on_state_change:
            self.on_state_change(self.state, self.get_game_info())

    def _notify_round_end(self, result: RoundResult) -> None:
        """通知本局结束"""
        if self.on_round_end:
            self.on_round_end(result)

    def _notify_action(self, action: PlayerAction) -> None:
        """通知操作执行"""
        if self.on_action:
            self.on_action(action)

    # ==================== 字符串表示 ====================

    def __repr__(self) -> str:
        pool = self.deck.remaining() if self.deck else 0
        return (
            f"GameEngine(round={self.round_num}, "
            f"state={self.state.name}, "
            f"current={self.current_player}, "
            f"pool={pool})"
        )
