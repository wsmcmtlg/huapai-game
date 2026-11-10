// ═══════════════════════════════════════════════════════════
// test_opp_meld_cards.js — 旁家明牌组是"字符串"的兼容回归（2026-11-06）
//
// 背景：实测"上家摸牌卡死"。根因是旁家明牌组存的是字字符串
//   opponentMelds[pi] = [{type:'zha', cards:['子','子','子','子']}]
// 而庄家明牌组存的是卡牌对象。判胡走 _huFlexPick / _preFromMeldList 时
// 对字符串取 .ch 得到 undefined → 抛错 → 旁家回合中断、停在"摸牌出牌中"。
//
// 本测试锁死：把字符串型明牌组喂给判胡链路，必须不抛错且能给出结果。
// ═══════════════════════════════════════════════════════════
'use strict';
const vm = require('vm');
const { loadGameCode, buildSandbox } = require('./measure_winrate.js');

let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log('✅ ' + name + (detail ? '  ' + detail : '')); }
  else { fail++; console.log('❌ ' + name + (detail ? '  ' + detail : '')); }
}

const loader = loadGameCode();
const { ctx, vmctx } = buildSandbox(202611111);
vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
for (const c of loader.chunks) { try { vm.runInContext(c, vmctx); } catch (e) {} }

// 旁家手牌 + 字符串型明牌组（模拟真实数据结构）
const hand = ['上', '大', '人', '可', '知', '礼', '二', '四', '六', '八', '十', '子', '土', '化', '千', '三'];
const melds = [
  { type: 'zha', cards: ['五', '五', '五', '五'] },
  { type: 'pen', cards: ['子', '子', '子'] }
];

const res = vm.runInContext(`(function(){
  var m = makeCardData;
  opponentHands[1] = ${JSON.stringify(hand)}.slice();
  opponentMelds[1] = ${JSON.stringify(melds)};
  var out = {};
  // ① _preFromMeldList 不应抛错，且能正确取到字
  try {
    var pre = _preFromMeldList(opponentMelds[1]);
    out.preOk = true;
    out.preChars = pre.map(function(p){ return p.type + ':' + (p.chars || []).join(''); });
  } catch (e) { out.preOk = false; out.preErr = e.message; }
  // ② 完整判胡链路不应抛错（字符串型明牌组）
  try {
    var cards = opponentHands[1].map(function(c){ return m(c, 'skin'); });
    var best = _huFlexPick(cards, opponentMelds[1]);
    out.flexOk = true;
    out.flexResult = best ? best.totalHu : 0;
  } catch (e) { out.flexOk = false; out.flexErr = e.message; }
  // ③ checkOpponentHu 不应抛错（它就是卡死现场的调用点）
  G.aiLevel = 3;
  try { var hu = checkOpponentHu(1); out.huOk = true; out.huWin = !!(hu && hu.isWin); }
  catch (e) { out.huOk = false; out.huErr = e.message; }
  return out;
})()`, vmctx);

check('_preFromMeldList 处理字符串明牌组不抛错', res.preOk === true, res.preOk ? (res.preChars || []).join(' ') : res.preErr);
check('_huFlexPick 处理字符串明牌组不抛错', res.flexOk === true, res.flexOk ? ('结果 ' + res.flexResult + ' 胡') : res.flexErr);
check('checkOpponentHu 处理字符串明牌组不抛错', res.huOk === true, res.huOk ? ('isWin=' + res.huWin) : res.huErr);

console.log('\n────────────────────────');
console.log(`结果: 通过 ${pass} / 失败 ${fail}`);
process.exit(fail === 0 ? 0 : 1);
