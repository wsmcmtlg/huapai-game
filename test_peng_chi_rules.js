// ═══════════════════════════════════════════════════════════
// test_peng_chi_rules.js — 碰/吃 规则约束回归测试（2026-11-05）
//
// 规则（用户口径）：
//   1. 所有玩家限碰两次；第三次碰牌只能用于捉铳（碰即成胡）
//   2. 吃牌只能是"吃进即胡"（吃统=捉铳），不存在"吃后听牌"
//   3. 统牌只能凑成碰或顺子（不能当坎、当眼）
//
// 手法：复用 measure_winrate.js 的提取/装载，把 analyzeHand 换成可控桩，
// 从而把"规则接线"与"算胡引擎"解耦单测（算胡引擎另有 39 项查表回归）。
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

function makeCase(penCount, fakeWin, ch) {
  const { vmctx } = buildSandbox(4242);
  vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
  for (const chunk of loader.chunks) { try { vm.runInContext(chunk, vmctx); } catch (e) {} }
  vm.runInContext(`
    // 旁家位1：手上 2 张 ch（可碰）+ 若干无关字
    opponentHands[1] = ${JSON.stringify([ch, ch, '上', '大', '人', '可', '知', '礼', '三', '五'])};
    opponentHands[2] = [];
    opponentMelds[1] = ${JSON.stringify(Array.from({ length: penCount }, () => ({ type: 'pen', chars: ['八', '八', '八'] })))};
    opponentMelds[2] = [];
    __fakeWin = ${fakeWin ? 'true' : 'false'};
    // analyzeHand 桩：只看 __fakeWin，不看真实牌型
    analyzeHand = function(cards, melds) {
      if (__fakeWin) return { isWin: true, totalHu: 30, melds: [], mainJin: '七' };
      return { isWin: false, totalHu: 0, melds: [], mainJin: '七' };
    };
  `, vmctx);
  const r = vm.runInContext(`_aiCheckOpponentChi(1, ${JSON.stringify(ch)})`, vmctx);
  return { r, vmctx };
}

// ── 用例 1：碰满两次 + 吃了/碰了都不能胡 → 不允许任何吃碰 ──
{
  const { r } = makeCase(2, false, '八');
  check('限两碰：已有 2 碰且非胡 → 不吃不碰', r === null, `结果=${JSON.stringify(r)}`);
}

// ── 用例 2：碰满两次 + 碰即胡 → 允许（第三次碰=捉铳）──
{
  const { r } = makeCase(2, true, '八');
  check('限两碰：已有 2 碰但碰即胡 → 允许捉铳',
    !!r && (r.chiType === '碰' || r.chiType === '顺'), `结果=${JSON.stringify(r)}`);
}

// ── 用例 3：零碰 + 不能胡 → 不允许吃（吃只能吃即胡）──
{
  const { r } = makeCase(0, false, '八');
  check('吃统=捉铳：不能胡时不允许吃（无进取吃）', r === null, `结果=${JSON.stringify(r)}`);
}

// ── 用例 4：零碰 + 吃即胡 → 允许 ──
{
  const { r } = makeCase(0, true, '八');
  check('吃统=捉铳：吃即胡时允许', !!r, `结果=${JSON.stringify(r)}`);
}

// ── 用例 5：进取性吃通道彻底移除（源码级断言）──
{
  const fs = require('fs');
  const src = fs.readFileSync('step5-hu.html', 'utf8');
  check('进取性吃 _aggrChiOk 已从源码移除', !/function\s+_aggrChiOk/.test(src) && !/_aggrChiOk\s*\(/.test(src));
}

// ── 用例 6：限两碰的源码级断言（庄家/旁家都要有）──
{
  const fs = require('fs');
  const src = fs.readFileSync('step5-hu.html', 'utf8');
  check('庄家限两碰逻辑在位', /penCount\s*>=\s*2\)\s*canPen\s*=\s*false/.test(src));
  check('旁家限两碰逻辑在位', /oppPenCount\s*>=\s*2\)\s*continue/.test(src));
}

console.log('\n────────────────────────');
console.log(`结果: 通过 ${pass} / 失败 ${fail}`);
process.exit(fail === 0 ? 0 : 1);
