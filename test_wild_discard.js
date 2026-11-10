// ═══════════════════════════════════════════════════════════
// test_wild_discard.js — 赖子保护回归（2026-11-06）
//
// 规则：赖子允许打出（"赖子除非打出，不能与旁家见面"），
//      但实战中极少主动打 —— AI 不应主动打赖子。
// 本测试锁死：手中有非赖牌时，四个等级的出牌选择都不得是赖子。
// （ε 随机与各等级策略都会走到，故每个等级重复多次取样）
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
const { ctx, vmctx } = buildSandbox(202611110);
vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
for (const c of loader.chunks) { try { vm.runInContext(c, vmctx); } catch (e) {} }

// 手牌：含 2 张赖子 + 若干散牌（赖子对任何简单牌型都没贡献，最容易被当"没用的牌"打出去）
const HAND = ['赖', '赖', '上', '大', '人', '可', '知', '礼', '二', '四', '六', '八', '十', '子'];

const res = vm.runInContext(`(function(){
  var m = makeCardData;
  var out = {};
  [0,1,2,3].forEach(function(lv){
    G.aiLevel = lv;
    var hits = { total: 0, wild: 0 };
    for (var t = 0; t < 300; t++) {
      var hand = ${JSON.stringify(HAND)}.map(function(ch){ return m(ch, 'skin'); });
      var idx = aiPickDiscard(hand, 0);
      if (typeof idx !== 'number' || idx < 0 || idx >= hand.length) continue;
      hits.total++;
      if (hand[idx].ch === '赖') hits.wild++;
    }
    out['L' + lv] = hits;
  });
  // 极端情况：手里只剩赖子 → 允许打
  G.aiLevel = 3;
  var onlyWild = [m('赖','skin')];
  out.onlyWild = aiPickDiscard(onlyWild, 0);
  return out;
})()`, vmctx);

for (const lv of ['L0', 'L1', 'L2', 'L3']) {
  const h = res[lv];
  check(`${lv}：300 次出牌中从不主动打赖子`, h.wild === 0, `打赖 ${h.wild}/${h.total} 次`);
}
check('极端情况（只剩赖子）仍能正常出牌', res.onlyWild === 0, `返回下标 ${res.onlyWild}`);

console.log('\n────────────────────────');
console.log(`结果: 通过 ${pass} / 失败 ${fail}`);
process.exit(fail === 0 ? 0 : 1);
