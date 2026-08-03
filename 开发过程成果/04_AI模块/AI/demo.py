#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 对战演示脚本
================
运行 3 个 AI 玩家（简单/中等/简单）进行花牌对战。

用法:
    python demo.py                # 默认 5 局
    python demo.py --rounds 10    # 自定义局数
    python demo.py --seed 123     # 自定义随机种子
    python demo.py --verbose      # 显示每步操作
"""

import sys
import os
import argparse

# 确保能导入规则引擎和 AI 模块
_phase1_path = os.path.join(os.path.dirname(__file__), "..", "Phase 1 规则引擎")
if os.path.exists(_phase1_path) and _phase1_path not in sys.path:
    sys.path.insert(0, os.path.abspath(_phase1_path))

_ai_path = os.path.dirname(__file__)
if _ai_path not in sys.path:
    sys.path.insert(0, os.path.abspath(_ai_path))

from AI.controller import AIGameController


def main():
    parser = argparse.ArgumentParser(description="湖北公安花牌 AI 对战演示")
    parser.add_argument("--rounds", "-r", type=int, default=5, help="对战局数 (默认5)")
    parser.add_argument("--seed", "-s", type=int, default=None, help="随机种子")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示每步操作")
    parser.add_argument(
        "--config", "-c", type=str, default="0:simple,1:medium,2:simple",
        help="AI配置，格式: 玩家索引:策略 (simple/medium)"
    )
    args = parser.parse_args()

    # 解析 AI 配置
    ai_config = {}
    ai_names = []
    for item in args.config.split(","):
        parts = item.strip().split(":")
        idx = int(parts[0])
        strategy = parts[1]
        ai_config[idx] = strategy
        ai_names.append("AI-{}({})".format(idx, strategy))

    print("=" * 60)
    print("湖北公安花牌 - AI 对战演示")
    print("=" * 60)
    print("局数: {}".format(args.rounds))
    print("AI配置: {}".format(args.config))
    if args.seed is not None:
        print("种子: {}".format(args.seed))
    print()

    controller = AIGameController(
        ai_config=ai_config,
        player_names=ai_names,
        seed=args.seed,
        verbose=args.verbose,
    )

    log = controller.run_game(max_rounds=args.rounds)
    summary = log.summary()
    print(summary)

    total_rounds = len(log.round_results)
    total_decisions = len(log.decisions)
    msg = "\n总计 {} 局, {} 步决策".format(total_rounds, total_decisions)
    print(msg)

    hu_count = sum(1 for r in log.round_results if r.winner is not None)
    huang_count = sum(1 for r in log.round_results if r.winner is None)
    print("胡牌: {}局, 流局: {}局".format(hu_count, huang_count))


if __name__ == "__main__":
    main()
