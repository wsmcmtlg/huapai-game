#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════
// extract_core.js — extract_core.py 的等价 Node 移植版
// 从 step5-hu.html 按锚点提取核心规则引擎代码，供回归测试使用。
// （本机未安装 Python 时用此脚本，逻辑与 extract_core.py 完全一致）
//
// 用法:
//   node hu_tests/extract_core.js <step5-hu.html> <输出current.js> [<备份html> <输出before.js>]
// 示例:
//   node hu_tests/extract_core.js step5-hu.html hu_tests/hu_core_current.js \
//        step5-hu_backup_before_flowskin_swap.html hu_tests/hu_core_before.js
// ═══════════════════════════════════════════════════════════
'use strict';
const fs = require('fs');

// (段名, 起点锚点, 终点锚点[不含该行]) —— 与 extract_core.py 严格一致
const ANCHORS = [
  ['工具+常量', 'function charColor(ch) {', '/* ═══ 游戏状态机 ═══ */'],
  ['JING表', 'const JING_RED_TABLE = {', '/* ═══ 启动 ═══ */'],
  ['计胡函数', 'function _lookupJingHu(cards, mtype, isMain) {',
    'function _partition(counts, wildList, wildUsed, handCards, melds, depth, usedSet, results) {'],
  ['_partition', 'function _partition(counts, wildList, wildUsed, handCards, melds, depth, usedSet, results) {',
    'function analyzeHand(cards, preMelds) {'],
  ['analyzeHand组', 'function analyzeHand(cards, preMelds) {', '// 胡数→得分对照表（每5胡一档）'],
];

function findLine(lines, needle, start = 0) {
  for (let i = start; i < lines.length; i++) if (lines[i].includes(needle)) return i;
  return -1;
}

function extract(htmlPath, outPath) {
  const lines = fs.readFileSync(htmlPath, 'utf8').split('\n');
  const parts = [];
  for (const [name, startAnchor, endAnchor] of ANCHORS) {
    const s = findLine(lines, startAnchor);
    if (s < 0) { console.error(`[错误] 找不到起点锚点: ${startAnchor}`); return false; }
    const e = findLine(lines, endAnchor, s + 1);
    if (e < 0) { console.error(`[错误] 找不到终点锚点: ${endAnchor}`); return false; }
    parts.push(lines.slice(s, e).join('\n'));
  }
  fs.writeFileSync(outPath, parts.join('\n') + '\n');
  const lineCount = parts.reduce((n, p) => n + p.split('\n').length, 0);
  console.log(`[OK] ${outPath}  共 ${lineCount} 行（锚点提取）`);
  return true;
}

function main() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.log('用法: node hu_tests/extract_core.js <html> <out.js> [<备份html> <out_before.js>]');
    return 1;
  }
  let ok = extract(args[0], args[1]);
  if (args.length >= 4) ok = extract(args[2], args[3]) && ok;
  return ok ? 0 : 1;
}
process.exit(main());
