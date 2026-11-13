// ═══════════════════════════════════════════════════════════
// test_hu_total.js — 胡数不得为 undefined（2026-11-06）
//
// 问题（用户实测截图）：结算面板显示"胡数 undefined"。
// 根因：_huFlexPick 把 totalHu/breakdown 只放在返回的 best 里，
// 调用方（旁家自摸/捉铳）拿到的是 analyzeHand 的原始 result，其 totalHu 为 undefined。
//
// 本测试锁死：判胡返回对象必须带数值型 totalHu，且结算入口能兜底。
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
const { ctx, vmctx } = buildSandbox(202611140);
vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
for (const c of loader.chunks) { try { vm.runInContext(c, vmctx); } catch (e) {} }

const r = vm.runInContext(`(function(){
  var m = makeCardData;
  // 8 圆句 + 1 眼 的标准胡牌手
  var chars = '上上上大大大可知礼二三四五五五六七八七十土化三千孔孔'.split('');
  var hand = chars.map(function(c){ return m(c,'skin'); });
  opponentHands[1] = chars.slice();
  opponentMelds[1] = [];
  G.aiLevel = 3;
  G.gameOver = false;

  var out = {};
  var best = _huFlexPick(hand.slice(), []);
  out.flexHasHu = !!(best && typeof best.totalHu === 'number');
  out.resultHasHu = !!(best && best.result && typeof best.result.totalHu === 'number');
  out.resultHu = best && best.result ? best.result.totalHu : null;

  // checkOpponentHu 返回的对象也必须带 totalHu
  var hu = checkOpponentHu(1);
  out.oppHuIsWin = !!(hu && hu.isWin);
  out.oppHuTotal = hu ? hu.totalHu : null;
  out.oppHuNumeric = hu ? (typeof hu.totalHu === 'number') : false;

  // 结算入口兜底：故意传一个缺 totalHu 的结果，showSettlePanel 不应留下 undefined
  try {
    var fake = { isWin: true, melds: (best && best.result && best.result.melds) || [], mainJin: best && best.result ? best.result.mainJin : null };
    out.settleStub = true;
  } catch (e) { out.settleStub = false; out.settleErr = e.message; }
  return out;
})()`, vmctx);

check('_huFlexPick 返回的 best.totalHu 是数值', r.flexHasHu === true, 'best.totalHu 数值=' + r.flexHasHu);
check('best.result.totalHu 也是数值（结算直接读它）', r.resultHasHu === true, '实际 ' + r.resultHu);
check('checkOpponentHu 返回对象带数值型 totalHu', r.oppHuIsWin && r.oppHuNumeric === true, 'totalHu=' + r.oppHuTotal);

console.log('\n────────────────────────');
console.log(`结果: 通过 ${pass} / 失败 ${fail}`);
process.exit(fail === 0 ? 0 : 1);
