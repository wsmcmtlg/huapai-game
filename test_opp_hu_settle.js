// ═══════════════════════════════════════════════════════════
// test_opp_hu_settle.js — 旁家胡牌必须有结算（2026-11-06）
//
// 问题（用户实测）：下家胡牌后没有结算面板、也没有任何后续动作，
// 只有回合显示"下家胡牌"，流程卡死，只能重载。
// 根因：opponentHu 只被调用、从未定义 → 抛 ReferenceError。
//
// 本测试锁死：opponentHu 必须存在，且调用后 ①gameOver=true ②结算面板被写入内容
// ═══════════════════════════════════════════════════════════
'use strict';
const vm = require('vm');
const { loadGameCode, buildSandbox } = require('./measure_winrate.js');

let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log('✅ ' + name + (detail ? '  ' + detail : '')); }
  else { fail++; console.log('❌ ' + name + (detail ? '  ' + detail : '')); }
}

const logs = [];
const loader = loadGameCode();
const { ctx, vmctx } = buildSandbox(202611130);
vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
ctx.console = { log: (...a) => logs.push(a.join(' ')), warn: (...a) => logs.push(a.join(' ')), error: (...a) => logs.push(a.join(' ')), info(){} };
for (const c of loader.chunks) { try { vm.runInContext(c, vmctx); } catch (e) {} }

// 记录 DOM 写入，用于断言"结算面板被渲染"
const els = {};
function fakeEl(id) {
  const el = {
    id, innerHTML: '', textContent: '', dataset: {}, style: { display: '' },
    classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
    appendChild(){}, prepend(){}, insertBefore(){}, removeChild(){}, remove(){}, setAttribute(){},
    getAttribute(){ return null; }, addEventListener(){}, focus(){}, scrollIntoView(){},
    querySelector(){ return fakeEl('q'); }, querySelectorAll(){ return []; },
    getBoundingClientRect(){ return {left:0,top:0,right:0,bottom:0,width:0,height:0}; }
  };
  return el;
}
ctx.document = new Proxy({}, {
  get(t, k) {
    if (k === 'getElementById') return (id) => { if (!els[id]) els[id] = fakeEl(id); return els[id]; };
    if (k === 'createElement') return (tag) => fakeEl('new-' + tag);
    if (k === 'querySelector') return () => fakeEl('q');
    if (k === 'querySelectorAll') return () => [];
    if (k === 'addEventListener') return () => {};
    if (k === 'body') return fakeEl('body');
    return () => fakeEl(String(k));
  }
});

const r = vm.runInContext(`(function(){
  var m = makeCardData;
  G.aiLevel = 3;
  G.gameOver = false;
  // 造一个能胡的旁家手牌：8 圆句 + 1 眼
  var chars = '上上上大大大可知礼二三四五五五六七八七十土化三千孔孔'.split('');
  opponentHands[1] = chars.map(function(c){ return c; });
  opponentMelds[1] = [];
  opponentHands[2] = []; opponentMelds[2] = [];
  G._pendingOppWin = null;
  var out = { fnType: typeof opponentHu };
  // 用桩捕获"是否真的调用了结算面板"（比断言 DOM 内容更稳、更直接）
  var settleCalls = 0, settleWinner = -1;
  var origSettle = showSettlePanel;
  showSettlePanel = function(pi, res, wt) { settleCalls++; settleWinner = pi; };
  try { opponentHu(1, '自摸'); out.ok = true; } catch (e) { out.ok = false; out.err = e.message; }
  showSettlePanel = origSettle;
  out.gameOver = G.gameOver;
  out.settleCalls = settleCalls;
  out.settleWinner = settleWinner;
  return out;
})()`, vmctx);

check('opponentHu 已定义（此前缺失导致 ReferenceError）', r.fnType === 'function', 'typeof = ' + r.fnType);
check('调用 opponentHu 不抛错', r.ok === true, r.err || '');
check('调用后本局结束（gameOver=true）', r.gameOver === true, 'gameOver=' + r.gameOver);
const settle = els['settle-container'];
check('旁家胡牌会调用结算面板（不再静默卡死）', r.settleCalls === 1 && r.settleWinner === 1, '调用 ' + r.settleCalls + ' 次，赢家位 ' + r.settleWinner);

console.log('[测试看到的流程日志]'); logs.slice(-6).forEach(l => console.log('   ' + l));
console.log('\n────────────────────────');
console.log(`结果: 通过 ${pass} / 失败 ${fail}`);
process.exit(fail === 0 ? 0 : 1);
