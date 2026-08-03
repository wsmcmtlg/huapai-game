"""
run_regression_1500.py — scoring_v3 查表法版 1500 局回归测试
================================================================
模拟完整对局流程：发牌 → 扎牌 → 摸打 → 胡牌/流局
验证 scoring_v3 在真实引擎环境中无异常。
"""
import sys, os, time, random, traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine import GameEngine, EngineState, RoundResult
from core.scoring import ScoreCalculator, Meld
from core.analyzer import HandAnalyzer
from core.melds import MeldType, WinType, MIN_HU_SCORE, ActionPriority
from core.actions import ActionValidator


def run_single_round(engine: GameEngine, verbose: bool = False) -> RoundResult:
    """运行一局完整对局

    策略: 简单AI — 随机出牌, 优先执行胡/对/招/扎操作
    """
    engine._start_new_round()

    # 1. 反向扎牌阶段
    zha_actions = engine.process_zha_phase()

    # 2. 庄家天胡判定
    tian_hu = engine.check_dealer_tian_hu()
    if tian_hu:
        if verbose:
            print(f"  [天胡] {engine.players[tian_hu.winner].name} {tian_hu.total_hu}胡")
        return tian_hu

    # 3. 主循环: 摸牌 → 出牌 → 响应
    engine.state = EngineState.DEALER_DISCARD
    engine.current_player = engine.dealer

    max_turns = 500  # 安全上限
    turns = 0

    while turns < max_turns:
        turns += 1

        # 流局检查
        if engine.check_liuju():
            return engine.handle_liuju()

        player = engine.players[engine.current_player]
        player.sort_hand()

        # ---- 摸牌 (庄家首轮已发牌不需摸) ----
        if engine.state == EngineState.DEALER_DISCARD:
            pass  # 庄家首轮不出牌, 直接出
        elif engine.state in (EngineState.DRAW_CARD, EngineState.PLAYER_DISCARD,
                               EngineState.PEN_DISCARD):
            card = engine.draw_card(engine.current_player)
            if card is None:
                return engine.handle_liuju()

            # 自摸检查
            self_actions = engine.check_self_actions(engine.current_player)
            if self_actions and self_actions[0].action_type == ActionPriority.HU:
                action = self_actions[0]
                result = engine.execute_action(action)
                if result and isinstance(result, RoundResult):
                    if verbose:
                        print(f"  [自摸] {player.name} {action.description}")
                    return result

            # 扎牌检查
            zha_list = [a for a in self_actions if a.action_type == ActionPriority.ZHA]
            if zha_list:
                engine.execute_action(zha_list[0])

            # 泛牌检查
            fan_list = [a for a in self_actions if a.action_type == ActionPriority.FAN]
            if fan_list:
                engine.execute_action(fan_list[0])

        # ---- 出牌 ----
        if not player.hand:
            # 手牌为空(可能全做成meld了), 检查余牌
            if engine.check_liuju():
                return engine.handle_liuju()
            card = engine.draw_card(engine.current_player)
            if card is None:
                return engine.handle_liuju()

        # 选择出牌: 优先打非精非赖的散牌
        hand = player.hand
        if not hand:
            return engine.handle_liuju()

        # 简单策略: 打第一张
        card_to_play = hand[0]
        played = engine.play_card(engine.current_player, card_to_play)
        if not played:
            # 尝试其他牌
            played = False
            for c in hand:
                if engine.play_card(engine.current_player, c):
                    card_to_play = c
                    played = True
                    break
            if not played:
                if verbose:
                    print(f"  [异常] {player.name} 无法出牌, hand={len(player.hand)}")
                return engine.handle_liuju()

        # ---- 旁家响应检查 ----
        actions_by_player = engine.check_other_players_actions(
            card_to_play, engine.current_player
        )

        if actions_by_player:
            best_action = engine.resolve_actions(actions_by_player)
            if best_action:
                if best_action.action_type == ActionPriority.HU:
                    result = engine.execute_action(best_action)
                    if result and isinstance(result, RoundResult):
                        if verbose:
                            winner = engine.players[result.winner]
                            print(f"  [捉统] {winner.name} {best_action.description}")
                        return result
                else:
                    engine.execute_action(best_action)
                    # 对/招后当前玩家变成操作者, 需要出牌
                    engine.state = EngineState.PLAYER_DISCARD
                    continue  # 不推进, 让操作者出牌

        # 推进到下一玩家
        engine.advance_turn()

    # 超过回合上限, 流局
    if verbose:
        print(f"  [超时] 超过{max_turns}回合, 流局")
    return engine.handle_liuju()


def run_regression(num_rounds: int = 1500, verbose_every: int = 100) -> dict:
    """运行多局回归测试

    Returns:
        统计数据
    """
    stats = {
        "total": num_rounds,
        "win": 0,
        "huang_zhuang": 0,
        "zi_mo": 0,
        "zhuo_tong": 0,
        "tian_hu": 0,
        "errors": 0,
        "error_details": [],
        "hu_scores": [],
        "avg_hu": 0,
        "max_hu": 0,
        "min_hu": float('inf'),
        "main_jin_dist": {},
        "winner_dist": {},
        "elapsed": 0,
    }

    print(f"{'='*60}")
    print(f"scoring_v3 回归测试: {num_rounds} 局")
    print(f"{'='*60}")

    start = time.time()
    for i in range(num_rounds):
        try:
            engine = GameEngine()
            result = run_single_round(engine, verbose=(i % verbose_every == 0 and verbose_every <= 10))

            if result.win_type == WinType.HUANG_ZHUANG:
                stats["huang_zhuang"] += 1
            else:
                stats["win"] += 1
                stats["hu_scores"].append(result.total_hu)
                if result.is_zi_mo:
                    stats["zi_mo"] += 1
                else:
                    stats["zhuo_tong"] += 1
                if result.win_type == WinType.TIAN_HU:
                    stats["tian_hu"] += 1
                stats["max_hu"] = max(stats["max_hu"], result.total_hu)
                stats["min_hu"] = min(stats["min_hu"], result.total_hu)

                # 主精分布
                mj = result.main_jin or "?"
                stats["main_jin_dist"][mj] = stats["main_jin_dist"].get(mj, 0) + 1

                # 赢家分布
                wn = f"P{result.winner}" if result.winner is not None else "?"
                stats["winner_dist"][wn] = stats["winner_dist"].get(wn, 0) + 1

        except Exception as e:
            stats["errors"] += 1
            detail = f"第{i+1}局: {type(e).__name__}: {str(e)[:100]}"
            stats["error_details"].append(detail)
            if len(stats["error_details"]) <= 5:
                traceback.print_exc()

        # 进度报告
        if (i + 1) % verbose_every == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            print(f"  [{i+1:4d}/{num_rounds}] "
                  f"胡:{stats['win']} 流局:{stats['huang_zhuang']} "
                  f"错误:{stats['errors']} "
                  f"({rate:.1f}局/s)")

    stats["elapsed"] = time.time() - start
    if stats["hu_scores"]:
        stats["avg_hu"] = sum(stats["hu_scores"]) / len(stats["hu_scores"])
    if stats["min_hu"] == float('inf'):
        stats["min_hu"] = 0

    return stats


def print_report(stats: dict) -> None:
    """打印统计报告"""
    s = stats
    print(f"\n{'='*60}")
    print(f"回归测试报告 — scoring_v3 查表法版")
    print(f"{'='*60}")

    print(f"\n基本统计:")
    print(f"  总局数:     {s['total']}")
    print(f"  胡牌局数:   {s['win']} ({s['win']/s['total']*100:.1f}%)")
    print(f"  流局(黄庄): {s['huang_zhuang']} ({s['huang_zhuang']/s['total']*100:.1f}%)")
    print(f"  错误:       {s['errors']}")
    print(f"  用时:       {s['elapsed']:.1f}s ({s['total']/s['elapsed']:.1f}局/s)")

    if s['win'] > 0:
        print(f"\n胡牌类型:")
        print(f"  自摸:       {s['zi_mo']} ({s['zi_mo']/s['win']*100:.1f}%)")
        print(f"  捉统:       {s['zhuo_tong']} ({s['zhuo_tong']/s['win']*100:.1f}%)")
        print(f"  天胡:       {s['tian_hu']}")

        print(f"\n胡数分布:")
        print(f"  最低:       {s['min_hu']}胡")
        print(f"  最高:       {s['max_hu']}胡")
        print(f"  平均:       {s['avg_hu']:.1f}胡")

    if s['main_jin_dist']:
        print(f"\n主精分布:")
        for k, v in sorted(s['main_jin_dist'].items()):
            bar = "█" * int(v / max(s['main_jin_dist'].values()) * 30)
            print(f"  {k}: {v:4d}局 {bar}")

    if s['winner_dist']:
        print(f"\n赢家座位:")
        for k, v in sorted(s['winner_dist'].items()):
            print(f"  {k}: {v:4d}局")

    if s['error_details']:
        print(f"\n错误详情 (前{min(len(s['error_details']),5)}条):")
        for e in s['error_details'][:5]:
            print(f"  {e}")

    # 验证结论
    print(f"\n{'='*60}")
    if s['errors'] == 0:
        print(f"结论: ✓ {s['total']}局全部通过, 0错误")
    else:
        print(f"结论: ✗ {s['total']}局中有{s['errors']}局异常")
    print(f"{'='*60}")


if __name__ == "__main__":
    stats = run_regression(num_rounds=1500, verbose_every=100)
    print_report(stats)
