"""
replay_text.py — 单局文字回放器 v2
====================================
通过hook引擎事件回调，完整记录一局对局的每个操作步骤，
并以格式化文字输出到终端。

改进:
  - 智能AI策略: 优先打单张散牌，保留对子/坎/顺子
  - 更清晰的操作图标
  - 胡牌时显示牌型拆分和计胡明细

使用方法:
    python replay_text.py              # 自动搜索胡牌局回放
    python replay_text.py --max 500    # 最多运行500局
    python replay_text.py --force      # 强制回放第1局
    python replay_text.py --number 42  # 回放第42局
    python replay_text.py --all        # 回放每一局
"""

import sys
import os
import argparse
import traceback
import time
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', '..', 'Desktop', 'My_LHP', 'Phase 1 规则引擎'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import GameEngine, EngineState, RoundResult
from core.melds import WinType, MeldType
from core.actions import ActionPriority
from core.scoring import ScoreCalculator


# ──────────────────────────────────────────────
# 牌面文字显示
# ──────────────────────────────────────────────

def card_to_str(card) -> str:
    """Card → 精简文字: [花]三  [皮]三  三  [赖]"""
    if card.is_wild:
        return "[赖]"
    prefix = ""
    if card.is_jin:
        prefix = "花" if card.is_flower else "皮"
    return prefix + card.char


def hand_to_str(hand) -> str:
    """手牌列表 → 紧凑字符串"""
    return " ".join(card_to_str(c) for c in hand)


def meld_to_str(meld) -> str:
    """Meld → 显示字符串"""
    chars = " ".join(card_to_str(c) for c in meld.cards)
    type_label = {
        MeldType.SEQUENCE: "顺",
        MeldType.KAN: "坎",
        MeldType.PEN: "碰",
        MeldType.ZHAO: "招",
        MeldType.ZHA: "杠",
        MeldType.CHUAN: "穿",
        MeldType.FAN: "泛",
        MeldType.PAIR: "对",
    }.get(meld.meld_type, meld.meld_type.value)
    return f"[{type_label}] {chars}"


# ──────────────────────────────────────────────
# 回放记录器
# ──────────────────────────────────────────────

class ReplayRecorder:
    def __init__(self):
        self.events = []
        self.step = 0

    def record(self, ev_type, player="", detail="", hand=None, melds=None, pool=0):
        self.step += 1
        self.events.append({
            "step": self.step, "type": ev_type, "player": player,
            "detail": detail, "hand": hand, "melds": melds, "pool": pool,
        })


# ──────────────────────────────────────────────
# 智能出牌策略
# ──────────────────────────────────────────────

def smart_choose_discard(hand):
    """智能选牌: 打单张散牌，保留对子/坎/顺子

    优先级: 打count=1的非精非赖牌 > 打count=1的精牌 > 打count=2的散牌
    从不打赖子，尽量不打精牌
    """
    char_counts = Counter(c.char for c in hand)

    def discard_priority(c):
        cnt = char_counts[c.char]
        return (c.is_wild, -cnt, c.is_jin)

    return sorted(hand, key=discard_priority, reverse=True)


# ──────────────────────────────────────────────
# 单局运行器（带事件记录）
# ──────────────────────────────────────────────

def run_recorded_round(engine) -> dict:
    """运行一局并记录事件"""
    rec = ReplayRecorder()
    players = engine.players

    engine._start_new_round()

    # ── 发牌 ──
    mj = engine.deck.main_jin
    mj_char = mj.char if mj else "?"
    vj = engine.deck.vice_jin
    vj_char = vj.char if vj else "无"

    rec.record("发牌", detail=f"庄家={players[0].name} | 主精={mj_char} | 副精={vj_char} | 余牌={engine.deck.remaining()}")

    for i, p in enumerate(players):
        p.sort_hand()
        rec.record("手牌", player=p.name,
                   detail=f"{'(庄)' if i==0 else ''} {len(p.hand)}张",
                   hand=list(p.hand))

    # ── 扎牌阶段 ──
    zha_actions = engine.process_zha_phase()
    for za in zha_actions:
        p = players[za.source_player]
        p.sort_hand()
        rec.record("扎牌", player=p.name, detail=za.description,
                   hand=list(p.hand), pool=engine.deck.remaining())

    # ── 天胡 ──
    tian_hu = engine.check_dealer_tian_hu()
    if tian_hu:
        rec.record("天胡", player=players[tian_hu.winner].name,
                   detail=f"{tian_hu.total_hu}胡 {tian_hu.win_type.value}")
        return {"result": tian_hu, "events": rec.events, "main_jin": mj_char,
                "players": players, "recorder": rec}

    # ── 主循环 ──
    engine.state = EngineState.DEALER_DISCARD
    engine.current_player = engine.dealer
    max_turns = 500

    for turns in range(1, max_turns + 1):
        if engine.check_liuju():
            rec.record("流局", detail="余牌耗尽")
            return {"result": engine.handle_liuju(), "events": rec.events,
                    "main_jin": mj_char, "players": players, "recorder": rec}

        player = players[engine.current_player]
        player.sort_hand()

        # 摸牌
        if engine.state != EngineState.DEALER_DISCARD:
            card = engine.draw_card(engine.current_player)
            if card is None:
                rec.record("流局", detail="摸牌为空")
                return {"result": engine.handle_liuju(), "events": rec.events,
                        "main_jin": mj_char, "players": players, "recorder": rec}

            rec.record("摸牌", player=player.name, detail=card_to_str(card),
                       hand=list(player.hand), pool=engine.deck.remaining())

            # 自摸
            self_actions = engine.check_self_actions(engine.current_player)
            hu = [a for a in self_actions if a.action_type == ActionPriority.HU]
            if hu:
                p = players[hu[0].source_player]
                p.sort_hand()
                rec.record("自摸胡", player=p.name, detail=hu[0].description,
                           hand=list(p.hand))
                result = engine.execute_action(hu[0])
                if isinstance(result, RoundResult):
                    _record_hu_result(rec, result, p)
                    return {"result": result, "events": rec.events,
                            "main_jin": mj_char, "players": players, "recorder": rec}

            for atype in (ActionPriority.ZHA, ActionPriority.FAN):
                acts = [a for a in self_actions if a.action_type == atype]
                if acts:
                    p = players[acts[0].source_player]
                    p.sort_hand()
                    type_label = "暗杠" if atype == ActionPriority.ZHA else "泛牌"
                    rec.record(type_label, player=p.name, detail=acts[0].description,
                               hand=list(p.hand), pool=engine.deck.remaining())
                    engine.execute_action(acts[0])

        # 出牌
        if not player.hand:
            if engine.check_liuju():
                return {"result": engine.handle_liuju(), "events": rec.events,
                        "main_jin": mj_char, "players": players, "recorder": rec}
            card = engine.draw_card(engine.current_player)
            if card is None:
                return {"result": engine.handle_liuju(), "events": rec.events,
                        "main_jin": mj_char, "players": players, "recorder": rec}

        discard_list = smart_choose_discard(player.hand)
        played_card = None
        for c in discard_list:
            if engine.play_card(engine.current_player, c):
                played_card = c
                break

        if played_card is None:
            rec.record("异常", player=player.name, detail=f"无法出牌, 手牌{len(player.hand)}张")
            return {"result": engine.handle_liuju(), "events": rec.events,
                    "main_jin": mj_char, "players": players, "recorder": rec}

        rec.record("出牌", player=player.name, detail=card_to_str(played_card),
                   hand=list(player.hand), pool=engine.deck.remaining())

        # 旁家响应
        resp = engine.check_other_players_actions(played_card, engine.current_player)
        if resp:
            best = engine.resolve_actions(resp)
            if best:
                p = players[best.source_player]
                p.sort_hand()
                atype = best.action_type
                type_map = {
                    ActionPriority.HU: ("捉统胡", True),
                    ActionPriority.PEN: ("对牌", False),
                    ActionPriority.ZHAO: ("招牌", False),
                    ActionPriority.CHUAN: ("穿牌", False),
                    ActionPriority.CHOW: ("吃牌", False),
                }
                label, is_hu = type_map.get(atype, (atype.name, False))

                rec.record(label, player=p.name, detail=best.description,
                           hand=list(p.hand), melds=list(p.melds),
                           pool=engine.deck.remaining() if atype in (ActionPriority.ZHAO, ActionPriority.CHUAN) else None)

                result = engine.execute_action(best)
                if isinstance(result, RoundResult):
                    _record_hu_result(rec, result, p)
                    return {"result": result, "events": rec.events,
                            "main_jin": mj_char, "players": players, "recorder": rec}
                elif atype in (ActionPriority.PEN, ActionPriority.ZHAO, ActionPriority.CHUAN, ActionPriority.CHOW):
                    engine.state = EngineState.PLAYER_DISCARD
                    continue  # 操作者出牌，不推进

        engine.advance_turn()

    rec.record("超时", detail=f"超过{max_turns}回合")
    return {"result": engine.handle_liuju(), "events": rec.events,
            "main_jin": mj_char, "players": players, "recorder": rec}


def _record_hu_result(rec, result, player):
    """记录胡牌结果"""
    player.sort_hand()
    hu_type = {WinType.ZI_MO: "自摸", WinType.ZHUO_TONG: "捉统",
               WinType.TIAN_HU: "天胡", WinType.DI_HU: "地胡"}.get(result.win_type, "?")
    rec.record("胡牌结算", player=player.name,
               detail=f"{result.total_hu}胡 | {hu_type} | 得{result.total_score}分",
               hand=list(player.hand), melds=list(player.melds))


# ──────────────────────────────────────────────
# 文字渲染器
# ──────────────────────────────────────────────

def render_replay(data: dict) -> str:
    lines = []
    result = data["result"]
    events = data["events"]
    mj = data["main_jin"]

    def add(s=""):
        lines.append(s)

    add()
    add("=" * 72)
    add("        湖北花牌 - 单局文字回放")
    add("=" * 72)

    # 结果头
    add()
    if result.win_type == WinType.HUANG_ZHUANG:
        add(f"  [ 流局 ] 黄庄")
    else:
        pn = data["players"][result.winner].name if result.winner is not None else "?"
        ht = {WinType.ZI_MO: "自摸", WinType.ZHUO_TONG: "捉统",
              WinType.TIAN_HU: "天胡", WinType.DI_HU: "地胡"}.get(result.win_type, str(result.win_type))
        add(f"  [ 胡 牌 ] {pn}  {result.total_hu}胡  {ht}  得{result.total_score}分")

    # 事件流
    for ev in events:
        t = ev["type"]
        step = ev["step"]
        pn = ev["player"]

        # 发牌
        if t == "发牌":
            add()
            add(f"  +{'='*66}+")
            add(f"  |  {ev['detail']}")
            add(f"  +{'-'*66}+")
            continue

        if t == "手牌":
            add(f"  | {pn:4s} {ev['detail']}")
            add(f"  |   {hand_to_str(ev['hand'])}")
            continue

        # 操作图标
        icons = {
            "扎牌": ">>>", "暗杠": "[4]", "穿牌": "[5]", "泛牌": "[*]",
            "摸牌": " ::", "出牌": " >>", "对牌": " <>", "招牌": " <+>",
            "吃牌": " <",  "天胡": "***", "自摸胡": " !!", "捉统胡": " !!",
            "胡牌结算": "===", "流局": "---", "异常": "???", "超时": "~~~",
        }
        icon = icons.get(t, "   ")
        is_major = t in ("扎牌", "暗杠", "穿牌", "泛牌", "天胡",
                          "自摸胡", "捉统胡", "胡牌结算", "流局")

        if is_major:
            add()
            add(f"  [{step:03d}] {icon} {pn:4s} {t}: {ev['detail']}")
        else:
            add(f"  [{step:03d}] {icon} {pn:4s} {t}: {ev['detail']}")

        # 手牌快照
        if ev["hand"] and t not in ("手牌", "发牌"):
            add(f"          手牌({len(ev['hand']):2d}): {hand_to_str(ev['hand'])}")

        # 明牌
        if ev.get("melds"):
            for m in ev["melds"]:
                add(f"          明牌: {meld_to_str(m)}")

        # 余牌
        if ev.get("pool") is not None and t not in ("手牌", "发牌"):
            add(f"          余牌: {ev['pool']}")

    # 胡牌牌型拆分
    if result.win_type != WinType.HUANG_ZHUANG:
        if hasattr(result, 'melds_detail') and result.melds_detail:
            add()
            add(f"  +{'='*66}+")
            add(f"  |  牌型拆分与计胡明细:")
            add(f"  +{'-'*66}+")

            calculator = ScoreCalculator()

            # 逐牌型计胡
            total_calc = 0
            for m in result.melds_detail:
                main_mark = " [主精]" if m.contains_main_jin else ""
                open_mark = "[明]" if m.is_open else "[暗]"

                # 根据牌型选择对应计胡方法
                mt = m.meld_type
                cards_tuple = tuple(m.cards)
                is_mj = m.contains_main_jin

                if mt == MeldType.KAN:
                    hu = calculator.calc_kan_hu(cards_tuple, is_main_jin=is_mj)
                elif mt == MeldType.PEN:
                    hu = calculator.calc_pen_hu(cards_tuple)
                elif mt == MeldType.ZHAO:
                    hu = calculator.calc_zhao_hu(cards_tuple, is_main_jin=is_mj)
                elif mt == MeldType.SEQUENCE:
                    chars_tuple = tuple(c.char for c in m.cards)
                    hu = calculator.calc_sequence_hu(cards_tuple, chars_tuple, is_main_jin=is_mj)
                elif mt == MeldType.PAIR:
                    hu = calculator.calc_pair_hu(cards_tuple, is_main_jin=is_mj)
                elif mt == MeldType.CHUAN:
                    hu = calculator.calc_chuan_hu(cards_tuple, is_main_jin=is_mj)
                elif mt == MeldType.FAN:
                    hu = calculator.calc_fan_hu(cards_tuple, is_main_jin=is_mj)
                elif mt == MeldType.ZHA:
                    hu = calculator.calc_zha_hu(cards_tuple, is_main_jin=is_mj)
                else:
                    hu = 0

                total_calc += hu
                add(f"  |  {meld_to_str(m):30s} {open_mark} {hu}胡{main_mark}")

            add(f"  +{'-'*66}+")
            add(f"  |  合计: {result.total_hu}胡 (计算:{total_calc}胡)  |  得分: {result.total_score}分")
            add(f"  +{'='*66}+")

    # 尾部统计
    add()
    rec = data.get("recorder")
    turn_count = rec.step if rec else "?"
    add(f"  总步骤: {len(events)}")
    add("=" * 72)
    add()
    return "\n".join(lines)


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="湖北花牌 - 单局文字回放器")
    parser.add_argument("--max", type=int, default=500, help="搜索胡牌局最大局数")
    parser.add_argument("--force", action="store_true", help="强制回放第1局")
    parser.add_argument("--number", type=int, default=None, help="回放第N局")
    parser.add_argument("--all", action="store_true", help="回放每一局(直到流局)")
    args = parser.parse_args()

    if args.number is not None:
        for _ in range(args.number - 1):
            GameEngine()
            run_recorded_round(GameEngine())
        engine = GameEngine()
        data = run_recorded_round(engine)
        print(render_replay(data))
        return

    if args.force:
        engine = GameEngine()
        data = run_recorded_round(engine)
        print(render_replay(data))
        return

    if args.all:
        round_num = 0
        while True:
            round_num += 1
            try:
                engine = GameEngine()
                data = run_recorded_round(engine)
                print(render_replay(data))
                input("按回车继续下一局...")
            except KeyboardInterrupt:
                print(f"\n已停止，共回放{round_num}局")
                break
        return

    # 默认: 搜索胡牌局
    print(f"正在搜索胡牌局 (最多{args.max}局, 智能AI策略)...")
    start = time.time()

    for i in range(args.max):
        try:
            engine = GameEngine()
            data = run_recorded_round(engine)
            result = data["result"]

            if result.win_type != WinType.HUANG_ZHUANG:
                elapsed = time.time() - start
                print(f"  第{i+1}局: {result.total_hu}胡 {result.win_type.value} ({elapsed:.1f}s)")
                print(render_replay(data))
                return
        except Exception as e:
            print(f"  第{i+1}局异常: {e}")
            traceback.print_exc()

    print(f"  {args.max}局均流局，回放最后一局...")
    engine = GameEngine()
    data = run_recorded_round(engine)
    print(render_replay(data))


if __name__ == "__main__":
    main()
