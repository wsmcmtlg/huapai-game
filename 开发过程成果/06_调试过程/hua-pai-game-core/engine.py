"""
花牌游戏 - 游戏引擎模块
核心调度器，管理游戏状态流转和操作处理。
"""

import random
from enum import Enum
from .card import Card, create_deck, shuffle_deck, deal, sort_cards
from .player import Player
from .melds import MeldType, WinType, FanType
from .analyzer import check_ting, can_pen, can_zhao, can_fan_from_discard
from .scoring import calc_total_score, find_best_zhu_jing


class GameState(Enum):
    """游戏状态"""
    INIT = "init"
    SHUFFLE = "shuffle"
    DEAL = "deal"
    ZHA_PHASE = "zha_phase"
    DEALER_CHECK_HU = "dealer_check_hu"
    DEALER_DISCARD = "dealer_discard"
    PLAYER_RESPONSE = "player_response"
    DRAW_CARD = "draw_card"
    SELF_CHECK = "self_check"
    PLAYER_DISCARD = "player_discard"
    PEN_DISCARD = "pen_discard"
    GAME_OVER = "game_over"
    SETTLE = "settle"


class GameEngine:
    """花牌游戏引擎"""

    ACTION_TIMEOUT = 20  # 普通操作20秒
    HU_TIMEOUT = 30      # 胡牌30秒

    def __init__(self):
        self.state = GameState.INIT
        self.players: list[Player] = []
        self.draw_pile: list[Card] = []
        self.round_number: int = 0
        self.current_player_idx: int = 0  # 当前操作玩家索引
        self.dealer_idx: int = 0           # 庄家索引
        self.last_discard: Card | None = None  # 最近打出的牌
        self.last_discard_player: int = -1
        self.winner: Player | None = None
        self.win_type: WinType | None = None
        self.game_log: list[dict] = []      # 对局日志（用于回放）

    # ============================================================
    # 游戏初始化
    # ============================================================

    def init_game(self, player_names: list[str] | None = None,
                  ai_players: list[int] | None = None) -> dict:
        """
        初始化游戏。
        player_names: 3个玩家名称
        ai_players: AI玩家索引列表
        """
        self.game_log = []
        if player_names is None:
            player_names = ["玩家1", "玩家2", "玩家3"]
        if ai_players is None:
            ai_players = [1, 2]

        self.players = []
        for i in range(3):
            p = Player(i, player_names[i], is_ai=(i in ai_players))
            self.players.append(p)

        return self._log_action("init", {"players": player_names, "ai": ai_players})

    def start_round(self) -> dict:
        """
        开始新一局。
        1. 洗牌
        2. 掷骰子定庄（首轮）或连庄/换庄
        3. 发牌
        """
        self.state = GameState.SHUFFLE
        self.winner = None
        self.win_type = None
        self.last_discard = None

        # 重置玩家状态
        for p in self.players:
            p.hand_cards = []
            p.open_melds = []
            p.hidden_melds = []
            p.discard_pile = []
            p.is_active = False
            p.hu_eligible = True

        # 洗牌
        deck = shuffle_deck(create_deck())

        # 首轮掷骰定庄
        if self.round_number == 0:
            dice = [random.randint(1, 6) for _ in range(3)]
            total = sum(dice)
            self.dealer_idx = total % 3
        # 非首轮：庄家索引不变（连庄或换庄在settle中处理）

        # 设置座位
        self.players[self.dealer_idx].is_dealer = True
        self.players[self.dealer_idx].seat_index = 0
        self.players[(self.dealer_idx + 1) % 3].seat_index = 1  # 下家
        self.players[(self.dealer_idx + 2) % 3].seat_index = 2  # 上家

        # 发牌
        hands, self.draw_pile = deal(deck)
        for i, p in enumerate(self.players):
            p.receive_cards(hands[i])

        self.round_number += 1
        self.state = GameState.ZHA_PHASE

        result = {
            "round": self.round_number,
            "dealer": self.dealer_idx,
            "dice": [random.randint(1, 6) for _ in range(3)] if self.round_number == 1 else None,
            "hands": {i: len(h) for i, h in hands.items()},
            "draw_pile_count": len(self.draw_pile),
        }
        self._log_action("start_round", result)
        return result

    # ============================================================
    # 反向扎牌阶段
    # ============================================================

    def zha_phase(self) -> dict:
        """
        反向扎牌阶段（上家→下家→庄家）。
        每个玩家可选择是否扎牌。
        """
        self.state = GameState.ZHA_PHASE
        order = self._get_reverse_order()
        results = []

        for pidx in order:
            player = self.players[pidx]
            opportunities = player.get_valid_actions_on_draw()
            zha_actions = [a for a in opportunities if a["action"] == "zha"]

            for action in zha_actions:
                if player.is_ai:
                    # AI决定是否扎牌
                    should_zha = self._ai_should_zha(player, action["char"])
                    if should_zha:
                        meld = player.execute_zha(action["char"])
                        if meld:
                            card = self.draw_pile.pop()  # 取最后一张
                            player.draw_card(card)
                            results.append({
                                "player": pidx, "action": "zha",
                                "char": action["char"],
                            })
                            self._log_action("zha", {
                                "player": pidx, "char": action["char"],
                            })

        self.state = GameState.DEALER_CHECK_HU
        return {"actions": results}

    def _ai_should_zha(self, player: Player, char: str) -> bool:
        """简单的AI扎牌决策"""
        # 如果扎牌后胡数够，就扎
        return random.random() < 0.6

    # ============================================================
    # 庄家天胡判定
    # ============================================================

    def dealer_check_hu(self) -> dict:
        """庄家天胡判定"""
        self.state = GameState.DEALER_CHECK_HU
        dealer = self.players[self.dealer_idx]
        hu_result = check_ting(dealer.get_hand_for_analysis())

        if hu_result["is_ting"]:
            self.winner = dealer
            self.win_type = WinType.TIAN_HU
            self.state = GameState.GAME_OVER
            self._log_action("tian_hu", {
                "player": self.dealer_idx,
                "score": hu_result["best_score"],
            })
            return {
                "hu": True, "type": "天胡",
                "player": self.dealer_idx,
                "score": hu_result["best_score"],
                "zhu_jing": hu_result["zhu_jing"],
            }

        self.state = GameState.DEALER_DISCARD
        return {"hu": False}

    # ============================================================
    # 出牌处理
    # ============================================================

    def dealer_discard(self, card_id: int) -> dict:
        """庄家出牌"""
        dealer = self.players[self.dealer_idx]
        card = dealer.discard(card_id)
        self.last_discard = card
        self.last_discard_player = self.dealer_idx
        self.state = GameState.PLAYER_RESPONSE
        self._log_action("discard", {
            "player": self.dealer_idx, "card": card.char, "card_id": card_id,
        })
        return self._resolve_player_response(card)

    def player_discard(self, card_id: int) -> dict:
        """当前玩家出牌"""
        player = self.players[self.current_player_idx]
        card = player.discard(card_id)
        self.last_discard = card
        self.last_discard_player = self.current_player_idx
        self.state = GameState.PLAYER_RESPONSE
        self._log_action("discard", {
            "player": self.current_player_idx,
            "card": card.char, "card_id": card_id,
        })
        return self._resolve_player_response(card)

    # ============================================================
    # 旁家响应判定
    # ============================================================

    def _resolve_player_response(self, discarded_card: Card) -> dict:
        """
        解析旁家对出牌的响应。
        按优先级: 胡 > 泛 > 招 > 对
        多家可同时对时，按逆时针顺序（下家优先）。
        """
        # 获取响应顺序（逆时针方向，即下家优先）
        discard_player = self.last_discard_player
        # 下家（逆时针下一个）
        xiajia = (discard_player + 1) % 3
        # 上家（顺时针下一个 = 逆时针上一个）
        shangjia = (discard_player + 2) % 3
        response_order = [xiajia, shangjia]

        # 收集所有响应
        all_responses = []
        for pidx in response_order:
            player = self.players[pidx]
            if not player.hu_eligible:
                continue
            actions = player.get_valid_actions_on_discard(discarded_card)
            if actions:
                all_responses.append((pidx, actions))

        if not all_responses:
            # 无人响应，轮到下家摸牌
            return self._next_turn()

        # 处理响应（按优先级）
        for pidx, actions in all_responses:
            for action in actions:
                if action["action"] == "hu":
                    return self._handle_hu_declare(
                        pidx, WinType.ZHUO_TONG,
                        action.get("score", 0))

        for pidx, actions in all_responses:
            for action in actions:
                if action["action"] == "fan":
                    return self._handle_fan(pidx, discarded_card, action)

        for pidx, actions in all_responses:
            for action in actions:
                if action["action"] == "zhao":
                    return self._handle_zhao(pidx, discarded_card)

        # 对牌（拦对）是可选操作，只有胡/泛/招是必选的
        pen_candidates = []
        for pidx, actions in all_responses:
            for action in actions:
                if action["action"] == "pen":
                    pen_candidates.append((pidx, action))

        # AI决策是否拦对（只有50%概率拦对）
        if pen_candidates:
            for pidx, action in pen_candidates:
                player = self.players[pidx]
                if player.is_ai:
                    # AI根据手牌质量决定是否拦对
                    from .analyzer import SEQUENCE_SET
                    hand_chars = [c.char for c in player.hand_cards]
                    same_count = sum(1 for c in player.hand_cards
                                     if c.char == discarded_card.char)
                    # 如果手中还有其他对子/顺子潜力，不拦对
                    has_other_pairs = any(
                        sum(1 for c in player.hand_cards if c.char == ch) >= 2
                        for ch in set(hand_chars) if ch != discarded_card.char
                    )
                    in_sequence = any(
                        discarded_card.char in seq
                        for seq in SEQUENCE_SET
                    )
                    # 如果拦对能组成有价值的坎牌才拦
                    want_pen = False
                    if same_count >= 2:  # 确实有2张
                        if not has_other_pairs:
                            want_pen = random.random() < 0.6
                        elif not in_sequence:
                            want_pen = random.random() < 0.3
                        else:
                            want_pen = random.random() < 0.1
                    
                    if want_pen:
                        return self._handle_pen(pidx, discarded_card)

        return self._next_turn()

    # ============================================================
    # 操作处理
    # ============================================================

    def _handle_hu_declare(self, player_idx: int, win_type: WinType,
                           score: int) -> dict:
        """处理胡牌声明"""
        self.winner = self.players[player_idx]
        self.win_type = win_type
        self.state = GameState.GAME_OVER
        self._log_action("hu", {
            "player": player_idx, "type": win_type.value,
            "score": score, "discard": self.last_discard.char if self.last_discard else None,
        })
        return {
            "action": "hu", "player": player_idx,
            "type": win_type.value, "score": score,
            "game_over": True,
        }

    def _handle_fan(self, player_idx: int, discarded_card: Card,
                    action: dict) -> dict:
        """处理泛牌"""
        player = self.players[player_idx]
        if action.get("fan_type") == "from_discard":
            meld = player.execute_fan_type1(discarded_card)
        else:
            meld = player.execute_fan_type2()

        if meld is None:
            return self._next_turn()

        # 取牌
        if not self.draw_pile:
            return self._handle_huang_zhuang()
        if action.get("fan_type") == "from_discard":
            card = self.draw_pile.pop(0)  # 第一张
        else:
            card = self.draw_pile.pop()   # 最后一张
        player.draw_card(card)

        self.current_player_idx = player_idx
        self.state = GameState.SELF_CHECK
        self._log_action("fan", {
            "player": player_idx, "char": meld.char,
            "fan_type": action.get("fan_type"),
        })

        # 泛牌后检查是否能胡
        return self._check_self_hu(player_idx)

    def _handle_zhao(self, player_idx: int, discarded_card: Card) -> dict:
        """处理招牌"""
        player = self.players[player_idx]
        meld = player.execute_zhao(discarded_card)
        if not self.draw_pile:
            return self._handle_huang_zhuang()
        card = self.draw_pile.pop(0)
        player.draw_card(card)

        self.current_player_idx = player_idx
        self.state = GameState.SELF_CHECK
        self._log_action("zhao", {
            "player": player_idx, "char": meld.char,
        })
        return self._check_self_hu(player_idx)

    def _handle_pen(self, player_idx: int, discarded_card: Card) -> dict:
        """处理对牌"""
        player = self.players[player_idx]
        meld = player.execute_pen(discarded_card)

        self.current_player_idx = player_idx
        self.state = GameState.PEN_DISCARD
        self._log_action("pen", {
            "player": player_idx, "char": meld.char,
        })

        return {
            "action": "pen", "player": player_idx,
            "char": meld.char,
            "must_discard": True,
        }

    def handle_pen_discard(self, card_id: int) -> dict:
        """对牌后出牌"""
        return self.player_discard(card_id)

    # ============================================================
    # 摸牌和自检
    # ============================================================

    def _next_turn(self) -> dict:
        """转移到下一个玩家摸牌"""
        if not self.draw_pile:
            return self._handle_huang_zhuang()

        # 操作权转移至下家（逆时针方向 = +1）
        next_player = (self.last_discard_player + 1) % 3
        self.current_player_idx = next_player
        self.state = GameState.DRAW_CARD

        # 从余牌池顶部摸牌
        card = self.draw_pile.pop(0)
        self.players[next_player].draw_card(card)

        self._log_action("draw", {
            "player": next_player, "card_id": card.id,
            "draw_pile_count": len(self.draw_pile),
        })

        return self._check_self_hu(next_player)

    def _check_self_hu(self, player_idx: int) -> dict:
        """自摸胡牌检查"""
        player = self.players[player_idx]
        if not player.hu_eligible:
            return {"action": "no_hu", "player": player_idx,
                    "must_discard": True}

        hu_result = check_ting(player.get_hand_for_analysis())
        if hu_result["is_ting"]:
            if player.is_ai:
                # AI自动胡牌
                return self._handle_hu_declare(
                    player_idx, WinType.ZI_MO, hu_result["best_score"])
            else:
                return {
                    "action": "can_hu", "player": player_idx,
                    "score": hu_result["best_score"],
                    "zhu_jing": hu_result["zhu_jing"],
                    "wait_hu_decision": True,
                }

        return {"action": "no_hu", "player": player_idx,
                "must_discard": True}

    def handle_zha_or_chuan(self, player_idx: int, action: str,
                            char: str) -> dict:
        """处理扎牌/穿牌操作"""
        player = self.players[player_idx]
        if action == "zha":
            meld = player.execute_zha(char)
        elif action == "chuan":
            meld = player.execute_chuan(char)
        else:
            return {"error": f"Unknown action: {action}"}

        if meld is None:
            return {"error": f"Cannot execute {action} for {char}"}

        # 从余牌池底部取牌
        if not self.draw_pile:
            return self._handle_huang_zhuang()
        card = self.draw_pile.pop()
        player.draw_card(card)

        self._log_action(action, {"player": player_idx, "char": char})

        # 操作后再次检查胡牌
        return self._check_self_hu(player_idx)

    def handle_hu_pass(self, player_idx: int) -> dict:
        """玩家放弃胡牌"""
        player = self.players[player_idx]
        player.hu_eligible = False
        self._log_action("hu_pass", {"player": player_idx})
        return {"action": "no_hu", "player": player_idx,
                "must_discard": True}

    def handle_swap_zha(self, player_idx: int, old_char: str,
                        new_char: str) -> dict:
        """处理换扎"""
        player = self.players[player_idx]
        success = player.execute_swap_zha(old_char, new_char)
        if success:
            # 换扎后取余牌池底部一张
            if self.draw_pile:
                card = self.draw_pile.pop()
                player.draw_card(card)
            self._log_action("swap_zha", {
                "player": player_idx,
                "old_char": old_char, "new_char": new_char,
            })
            return {"action": "swap_zha", "success": True}
        return {"action": "swap_zha", "success": False, "error": "换扎失败"}

    # ============================================================
    # 黄庄处理
    # ============================================================

    def _handle_huang_zhuang(self) -> dict:
        """黄庄"""
        self.win_type = WinType.HUANG_ZHUANG
        self.state = GameState.GAME_OVER
        self._log_action("huang_zhuang", {})
        return {
            "action": "huang_zhuang",
            "game_over": True, "type": "黄庄",
        }

    # ============================================================
    # 结算
    # ============================================================

    def settle(self) -> dict:
        """本局结算"""
        self.state = GameState.SETTLE

        result = {
            "round": self.round_number,
            "win_type": self.win_type.value if self.win_type else "黄庄",
            "winner": self.winner.id if self.winner else None,
            "scores": {},
            "next_dealer": self.dealer_idx,  # 默认连庄
        }

        if self.winner:
            # 计算得分
            score = self._calculate_game_score(self.winner)
            result["scores"][self.winner.id] = score

            # 判定连庄/换庄
            if self.win_type == WinType.TIAN_HU or self.win_type == WinType.ZI_MO:
                result["next_dealer"] = self.winner.id  # 连庄
            elif self.win_type == WinType.ZHUO_TONG:
                # 胡牌者连庄（文档说旁家胡牌则下家上庄）
                # 但捉统结果说"胡牌者连庄"
                result["next_dealer"] = self.winner.id
            elif self.win_type == WinType.DI_HU:
                result["next_dealer"] = (self.dealer_idx + 1) % 3
        else:
            # 黄庄，庄家连庄
            result["next_dealer"] = self.dealer_idx

        self._log_action("settle", result)
        return result

    def _calculate_game_score(self, winner: Player) -> int:
        """计算游戏得分"""
        # 简化版：通过听牌检测获取胡数
        hu_result = check_ting(winner.get_hand_for_analysis())
        hu_score = hu_result.get("best_score", 17)

        # 胡数转得分: 17-21→3分，每多5胡+1分
        if hu_score <= 21:
            points = 3
        else:
            points = 3 + (hu_score - 21 - 1) // 5 + 1
        return points

    # ============================================================
    # AI操作
    # ============================================================

    def ai_turn(self) -> dict:
        """AI执行当前回合操作"""
        player = self.players[self.current_player_idx]
        if not player.is_ai:
            return {"error": "Current player is not AI"}

        # 根据状态执行对应操作
        if self.state == GameState.SELF_CHECK:
            return self._ai_self_check(player)

        elif self.state == GameState.PEN_DISCARD:
            return self._ai_discard(player)

        return {"error": "AI cannot act in current state"}

    def _ai_self_check(self, player: Player) -> dict:
        """AI自检阶段"""
        actions = player.get_valid_actions_on_draw()

        for action in actions:
            if action["action"] == "hu":
                return self._handle_hu_declare(
                    self.current_player_idx, WinType.ZI_MO,
                    action["score"])

        for action in actions:
            if action["action"] in ("chuan", "zha"):
                if random.random() < 0.7:
                    return self.handle_zha_or_chuan(
                        self.current_player_idx, action["action"], action["char"])

        for action in actions:
            if action["action"] == "swap_zha":
                if random.random() < 0.3:
                    return self.handle_swap_zha(
                        self.current_player_idx,
                        action["old_char"], action["new_char"])

        return self._ai_discard(player)

    def _ai_discard(self, player: Player) -> dict:
        """AI出牌决策"""
        if not player.hand_cards:
            return {"error": "No cards to discard"}

        # 简单策略: 出关联度最低的牌
        card = self._ai_choose_discard(player)
        return self.player_discard(card.id)

    def _ai_choose_discard(self, player: Player) -> Card:
        """AI选择出哪张牌"""
        # 简单策略:
        # 1. 不出能组成顺子/刻子的牌
        # 2. 优先出散牌
        # 3. 如果都是散牌，随机出
        from .analyzer import SEQUENCE_SET

        best_card = None
        best_score = float('inf')

        for card in player.hand_cards:
            score = 0
            # 检查是否是顺子的一部分
            for seq in SEQUENCE_SET:
                if card.char in seq:
                    other_chars = [c for c in seq if c != card.char]
                    has_others = sum(1 for c in player.hand_cards
                                     if c.char in other_chars and c.id != card.id)
                    if has_others >= len(other_chars):
                        score -= 10  # 能组成顺子，优先保留

            # 检查是否有相同字面（可能形成坎）
            same_count = sum(1 for c in player.hand_cards
                           if c.char == card.char and c.id != card.id)
            if same_count >= 2:
                score -= 8  # 能形成坎牌，保留
            elif same_count == 1:
                score -= 3  # 有对子，较保留

            # 赖子保留价值高
            if card.is_wild:
                score -= 15

            # 红精保留价值高
            if card.is_jing and card.is_red:
                score -= 5

            if score < best_score:
                best_score = score
                best_card = card

        return best_card or player.hand_cards[0]

    # ============================================================
    # 辅助方法
    # ============================================================

    def _get_reverse_order(self) -> list[int]:
        """
        获取反向顺序（上家→下家→庄家）。
        上家 = (dealer+2)%3, 下家 = (dealer+1)%3, 庄家 = dealer
        """
        shangjia = (self.dealer_idx + 2) % 3
        xiajia = (self.dealer_idx + 1) % 3
        return [shangjia, xiajia, self.dealer_idx]

    def get_next_player(self) -> int:
        """获取下一个玩家（逆时针方向）"""
        return (self.current_player_idx + 1) % 3

    def is_game_over(self) -> bool:
        return self.state == GameState.GAME_OVER

    def get_game_state(self) -> dict:
        """获取当前游戏状态（用于前端显示）"""
        return {
            "state": self.state.value,
            "round": self.round_number,
            "dealer": self.dealer_idx,
            "current_player": self.current_player_idx,
            "draw_pile_count": len(self.draw_pile),
            "last_discard": self.last_discard.to_dict() if self.last_discard else None,
            "players": [p.to_dict() for p in self.players],
            "game_over": self.is_game_over(),
            "winner": self.winner.id if self.winner else None,
            "win_type": self.win_type.value if self.win_type else None,
        }

    def _log_action(self, action: str, data: dict) -> dict:
        """记录操作日志"""
        entry = {"action": action, "data": data}
        self.game_log.append(entry)
        return entry

    def get_game_log(self) -> list[dict]:
        """获取完整对局日志"""
        return self.game_log[:]

    def __repr__(self):
        return (f"GameEngine(state={self.state.value}, round={self.round_number}, "
                f"dealer={self.dealer_idx}, "
                f"draw_pile={len(self.draw_pile)})")
