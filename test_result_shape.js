// ═══════════════════════════════════════════════════════════
// test_result_shape.js — 判胡/听牌/结算 结果对象"形状"冒烟测试（2026-11-06）
//
// 背景：本轮连续出现三类同类 bug，都是"跨函数传数据字段没对齐"：
//   · opponentHu 未定义 → 旁家胡牌流程卡死
//   · _huFlexPick 不回写 totalHu → 结算显示 undefined
//   · showTingPanel 读 t.hu、calcTingChars 却给 totalHu → 听口胡数 undefined
//
// 本测试把"结果对象必须具备哪些字段"钉死，改坏了就红。
//
// 必需字段：
//   判胡结果：isWin(bool) / totalHu(number) / melds(array)
//   听口条目：ch(string) / totalHu(number) / remaining(number)
//   听牌渲染：HTML 里不得出现 "undefined"
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
const { ctx, vmctx } = buildSandbox(202611150);
vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
for (const c of loader.chunks) { try { vm.runInContext(c, vmctx); } catch (e) {} }

// 捕获 showTingPanel 实际生成的 HTML
const els = {};
function fakeEl(id) {
  const el = {
    id, innerHTML: '', textContent: '', dataset: {}, style: { display: '' },
    classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
    appendChild(child){ if (child && child.innerHTML) el.innerHTML += child.innerHTML; },
    prepend(){}, insertBefore(){}, removeChild(){}, remove(){}, setAttribute(){},
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

const WIN_HAND = '上上上大大大可知礼二三四五五五六七八七十土化三千孔孔'.split('');

const r = vm.runInContext(`(function(){
  var m = makeCardData;
  var out = {};
  G.aiLevel = 3; G.gameOver = false;

  // ① 判胡结果形状（_huFlexPick）
  var hand = ${JSON.stringify(WIN_HAND)}.map(function(c){ return m(c,'skin'); });
  var best = _huFlexPick(hand.slice(), []);
  out.flex = best ? {
    isWin: !!(best.result && best.result.isWin),
    hasTotal: typeof (best.result && best.result.totalHu) === 'number',
    meldsArr: Array.isArray(best.result && best.result.melds),
    breakdownArr: Array.isArray(best.result && best.result.breakdown)
  } : null;

  // ② checkOpponentHu 形状
  opponentHands[1] = ${JSON.stringify(WIN_HAND)}.slice();
  opponentMelds[1] = [];
  var hu = checkOpponentHu(1);
  out.oppHu = hu ? {
    isWin: !!hu.isWin,
    hasTotal: typeof hu.totalHu === 'number',
    meldsArr: Array.isArray(hu.melds),
    total: hu.totalHu
  } : null;

  // ③ 听口条目形状（calcTingChars）
  handCards = ${JSON.stringify(WIN_HAND.slice(0, 25))}.map(function(c){ return m(c,'skin'); });
  G.dealerMelds = [];
  var ting = calcTingChars();
  out.ting = {
    count: ting.length,
    allHaveCh: ting.every(function(t){ return typeof t.ch === 'string' && t.ch.length > 0; }),
    allHaveHu: ting.every(function(t){ return typeof t.totalHu === 'number'; }),
    allHaveRem: ting.every(function(t){ return typeof t.remaining === 'number'; })
  };

  // ④ 听牌卡片渲染不得出现 undefined
  try { showTingPanel({ tingChars: ting.slice(), tingType: '听牌' }); } catch (e) { out.renderErr = e.message; }
  out.htmlHasUndefined = (document.getElementById('ting-container').innerHTML || '').indexOf('undefined') >= 0;
  return out;
})()`, vmctx);

check('_huFlexPick 结果：isWin 布尔', !!(r.flex && typeof r.flex.isWin === 'boolean'), JSON.stringify(r.flex));
check('_huFlexPick 结果：totalHu 数值', !!(r.flex && r.flex.hasTotal), 'hasTotal=' + (r.flex && r.flex.hasTotal));
check('_huFlexPick 结果：melds / breakdown 是数组', !!(r.flex && r.flex.meldsArr && r.flex.breakdownArr), '');
check('checkOpponentHu 结果：isWin / totalHu / melds 齐全',
  !!(r.oppHu && r.oppHu.isWin && r.oppHu.hasTotal && r.oppHu.meldsArr), 'totalHu=' + (r.oppHu && r.oppHu.total));
check('calcTingChars 听口条目：ch / totalHu / remaining 齐全',
  !!(r.ting && r.ting.allHaveCh && r.ting.allHaveHu && r.ting.allHaveRem), '听口数 ' + (r.ting && r.ting.count));
check('听牌卡片渲染不出现 undefined', r.htmlHasUndefined === false, r.renderErr ? ('渲染异常: ' + r.renderErr) : '');

console.log('\n────────────────────────');
console.log(`结果: 通过 ${pass} / 失败 ${fail}`);
process.exit(fail === 0 ? 0 : 1);
