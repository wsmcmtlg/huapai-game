# -*- coding: utf-8 -*-
"""
从 step5-hu.html 提取核心规则引擎代码，供回归测试使用。
用锚点定位（而非硬编码行号），未来源码行号变化仍能正确提取。

用法:
    python hu_tests/extract_core.py <step5-hu.html路径> <输出current.js> [<备份html路径> <输出before.js>]
示例:
    python hu_tests/extract_core.py step5-hu.html hu_tests/hu_core_current.js step5-hu_backup_before_flowskin_swap.html hu_tests/hu_core_before.js
"""
import sys


def find_line(lines, needle, start=0):
    """返回包含 needle 的行下标，找不到返回 -1"""
    for i in range(start, len(lines)):
        if needle in lines[i]:
            return i
    return -1


ANCHORS = [
    # (段名, 起点锚点, 终点锚点[不含该行])
    ("工具+常量", "function charColor(ch) {", "/* ═══ 游戏状态机 ═══ */"),
    ("JING表", "const JING_RED_TABLE = {", "/* ═══ 启动 ═══ */"),
    ("计胡函数", "function _lookupJingHu(cards, mtype, isMain) {",
     "function _partition(counts, wildList, wildUsed, handCards, melds, depth, usedSet, results) {"),
    ("_partition", "function _partition(counts, wildList, wildUsed, handCards, melds, depth, usedSet, results) {",
     "function analyzeHand(cards, preMelds) {"),
    ("analyzeHand组", "function analyzeHand(cards, preMelds) {", "// 胡数→得分对照表（每5胡一档）"),
]


def extract(html_path, out_path):
    with open(html_path, encoding="utf-8") as f:
        lines = f.read().split("\n")

    parts = []
    for name, start_anchor, end_anchor in ANCHORS:
        s = find_line(lines, start_anchor)
        if s < 0:
            print(f"[错误] 找不到起点锚点: {start_anchor}")
            return False
        e = find_line(lines, end_anchor, s + 1)
        if e < 0:
            print(f"[错误] 找不到终点锚点: {end_anchor}")
            return False
        seg = "\n".join(lines[s:e])
        parts.append(seg)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts) + "\n")
    print(f"[OK] {out_path}  共 {sum(p.count(chr(10)) + 1 for p in parts)} 行（锚点提取）")
    return True


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return 1
    ok = extract(args[0], args[1])
    if len(args) >= 4:
        ok = extract(args[2], args[3]) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
