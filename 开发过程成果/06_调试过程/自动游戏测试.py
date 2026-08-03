"""
花牌游戏 - 自动化测试脚本 v3
正确区分庄家出牌和当前玩家出牌。
"""
import sys
import os
import random
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import GameEngine, GameState
from core.melds import WinType


def choose_discard(player):
    """选择出牌（简单策略）"""
    if not player.hand_cards:
        return None
    hand_chars = [c.char for c in player.hand_cards]
    from core.analyzer import SEQUENCE_SET

    best_card = None
    best_score = -float('inf')

    for card in player.hand_cards:
        score = 0
        same_count = sum(1 for c in player.hand_cards if c.char == card.char) - 1
        in_seq = False
        for seq in SEQUENCE_SET:
            if card.char in seq:
                needed = [c for c in seq if c != card.char]
                if sum(1 for n in needed if n in hand_chars) >= 1:
                    in_seq = True
                    break
        if same_count >= 2: score -= 10
        elif same_count == 1: score -= 5
        if in_seq: score -= 3
        if card.is_wild: score -= 20
        if score > best_score or best_card is None:
            best_score = score
            best_card = card
    return best_card or player.hand_cards[0]


def run_game(num_rounds=5, seed=42):
    """运行多局游戏"""
    random.seed(seed)
    engine = GameEngine()
    engine.init_game(
        [f"AI-{i+1}" for i in range(3)],
        ai_players=[0, 1, 2]
    )

    stats = {"hu": 0, "huang": 0, "errors": []}

    for round_num in range(num_rounds):
        try:
            result = engine.start_round()
            rn = engine.round_number
            dealer = engine.players[engine.dealer_idx]
            print(f"\n{'='*50}")
            print(f"第{rn}局 | 庄家: {dealer.name}(idx={engine.dealer_idx}) | 余牌: {len(engine.draw_pile)}")

            # 扎牌
            zha = engine.zha_phase()
            for a in zha["actions"]:
                print(f"  {engine.players[a['player']].name} 扎 [{a['char']}]")

            # 天胡
            hu = engine.dealer_check_hu()
            if hu.get("hu"):
                w = engine.players[hu["player"]]
                print(f"  天胡! {w.name} 胡数={hu.get('score','?')}")
                _settle(engine, stats)
                continue

            # === 核心循环 ===
            turn = 0
            max_turns = 300

            while turn < max_turns and not engine.is_game_over():
                state = engine.state
                turn += 1

                # --- 庄家出牌 ---
                if state == GameState.DEALER_DISCARD:
                    # dealer_discard 内部使用 self.dealer_idx
                    dealer = engine.players[engine.dealer_idx]
                    card = choose_discard(dealer)
                    if not card:
                        print(f"  [{turn}] 庄家 {dealer.name} 无牌可出!")
                        break
                    print(f"  [{turn}] 庄家 {dealer.name} 出 [{card.char}]")
                    engine.dealer_discard(card.id)
                    # 内部: _resolve_player_response -> 胡/泛/招/对/_next_turn
                    # _next_turn: 设置 current_player_idx, DRAW_CARD, 已摸牌
                    continue

                # --- 当前玩家需要操作 ---
                if state in (GameState.DRAW_CARD, GameState.SELF_CHECK):
                    current = engine.players[engine.current_player_idx]
                    
                    if state == GameState.DRAW_CARD:
                        # _next_turn 已经摸牌了，转 SELF_CHECK
                        engine.state = GameState.SELF_CHECK
                    
                    # ai_turn 处理 SELF_CHECK: 检查自摸胡/穿/扎/出牌
                    ai_result = engine.ai_turn()
                    action = ai_result.get("action", "")
                    
                    if action == "hu":
                        wt = ai_result.get("win_type", "自摸")
                        print(f"  [{turn}] {current.name} 胡牌! ({wt})")
                        continue  # GAME_OVER
                    
                    if action in ("pen", "zhao", "chuan", "zha"):
                        label = {
                            "pen": "拦对", "zhao": "招牌",
                            "chuan": "穿牌", "zha": "扎牌"
                        }[action]
                        char = ai_result.get("char", "")
                        print(f"  [{turn}] {current.name} {label}" +
                              (f" [{char}]" if char else ""))
                        # pen->PEN_DISCARD, zhao/chuan/zha->SELF_CHECK
                        continue
                    
                    if action == "no_hu":
                        # ai_turn -> _ai_discard -> player_discard -> 已出牌
                        # player_discard 内部调用 _resolve_player_response
                        # 可能转到 DRAW_CARD/ GAME_OVER / PEN_DISCARD
                        if ai_result.get("must_discard"):
                            # 检查 ai_turn 是否已经出了牌
                            # _ai_discard 调用 player_discard -> card已出手
                            pass
                        continue
                    
                    if "error" in ai_result:
                        # 手动处理
                        card = choose_discard(current)
                        if card:
                            print(f"  [{turn}] {current.name} 出 [{card.char}]")
                            engine.player_discard(card.id)
                        continue
                    
                    continue

                # --- 拦对后出牌 ---
                if state == GameState.PEN_DISCARD:
                    current = engine.players[engine.current_player_idx]
                    card = choose_discard(current)
                    if card:
                        print(f"  [{turn}] {current.name} 出 [{card.char}] (拦对后)")
                        engine.handle_pen_discard(card.id)
                        # handle_pen_discard = player_discard -> _resolve_player_response
                    else:
                        print(f"  [{turn}] {current.name} 拦对后无牌可出!")
                        break
                    continue

                # --- 需要出牌 (PLAYER_DISCARD) ---
                if state == GameState.PLAYER_DISCARD:
                    current = engine.players[engine.current_player_idx]
                    card = choose_discard(current)
                    if card:
                        print(f"  [{turn}] {current.name} 出 [{card.char}]")
                        engine.player_discard(card.id)
                    continue

                # --- 结束 ---
                if state in (GameState.GAME_OVER, GameState.SETTLE):
                    break

                # PLAYER_RESPONSE 不应到达（已在出牌时处理）
                if state == GameState.PLAYER_RESPONSE:
                    # 尝试推进：可能是无人响应
                    break

                print(f"  [{turn}] 未处理状态: {state.value}")
                break

            if turn >= max_turns:
                print(f"  [WARN] 达到最大回合 {max_turns}")

            _settle(engine, stats)

        except Exception as e:
            err_msg = f"第{round_num+1}局: {e}"
            stats["errors"].append(err_msg)
            print(f"  [ERROR] {err_msg}")
            traceback.print_exc()

    print(f"\n===== 测试完成 =====")
    print(f"共 {engine.round_number} 局 | 胡牌: {stats['hu']} | 黄庄: {stats['huang']}")
    if stats["errors"]:
        print(f"错误: {len(stats['errors'])}个")
        for e in stats["errors"]:
            print(f"  - {e}")
    return stats


def _settle(engine, stats):
    """结算"""
    if not engine.is_game_over():
        engine.state = GameState.GAME_OVER
    settle = engine.settle()
    if settle["winner"] is not None:
        w = engine.players[settle["winner"]]
        wt = settle.get("win_type", "")
        info = ""
        if "scores" in settle:
            parts = [f"{engine.players[pid].name}:{s}分"
                     for pid, s in settle["scores"].items()]
            info = " | ".join(parts)
        print(f"  >> {w.name} 获胜 ({wt}) {info}")
        stats["hu"] += 1
    else:
        print(f"  >> 黄庄")
        stats["huang"] += 1


if __name__ == "__main__":
    run_game(num_rounds=5, seed=42)
