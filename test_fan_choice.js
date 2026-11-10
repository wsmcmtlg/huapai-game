// ═══════════════════════════════════════════════════════════
// test_fan_choice.js — 泛牌"多候选必须可选"回归（2026-11-06）
//
// 背景（用户实测报告）：手中有「礼」招与「化」招，后来又摸到「礼」，
// 想留下来等「知」，结果系统直接替他决定泛哪一个，没有选择权。
//
// 规则：泛牌 = 招牌 + 第 5 张。当多个招牌都具备第 5 张时，
//       **必须由玩家选择泛哪一组**（可选"过"），不得由代码静默取第一个。
//
// 本测试锁定三点：
//   ① 单候选：G._fanChars 长度为 1，泛按钮文案为「泛」
//   ② 多候选：G._fanChars 覆盖全部候选，能调出选择框（不直接执行）
//   ③ 选择后：按所选字泛牌（dealerFan(ch) 生效），不再二次询问
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
const { ctx, vmctx } = buildSandbox(20261110);
vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
for (const c of loader.chunks) { try { vm.runInContext(c, vmctx); } catch (e) {} }

// ── 可记录的 DOM 替身 ──
const els = {};
const rec = { created: [], dialogOpened: 0, fanCalled: [] };
function fakeEl(id) {
  const el = {
    id, innerHTML: '', textContent: '', dataset: {}, style: { display: '' },
    classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
    appendChild(){}, prepend(){}, insertBefore(){}, removeChild(){}, remove(){}, setAttribute(){}, getAttribute(k){ return el.dataset[k.replace('data-','')]; },
    addEventListener(){}, getBoundingClientRect(){ return {left:0,top:0,right:0,bottom:0,width:0,height:0}; },
    querySelector(sel){ return fakeEl('q'); }, querySelectorAll(sel){ return el._children || []; }, focus(){}, scrollIntoView(){}
  };
  return el;
}
ctx.document = new Proxy({}, {
  get(t, k) {
    if (k === 'getElementById') return (id) => { if (!els[id]) els[id] = fakeEl(id); return els[id]; };
    if (k === 'createElement') return (tag) => { const e = fakeEl('new-' + tag); rec.created.push(e); return e; };
    if (k === 'querySelector') return () => null;
    if (k === 'querySelectorAll') return () => [];
    if (k === 'addEventListener') return () => {};
    if (k === 'body') return fakeEl('body');
    return () => fakeEl(String(k));
  }
});

function setup(meldChars, handChars, drawChar) {
  Object.keys(els).forEach(k => delete els[k]);
  rec.created.length = 0; rec.dialogOpened = 0; rec.fanCalled.length = 0;
  return vm.runInContext(`(function(){
    var m = makeCardData;
    handCards = ${JSON.stringify(handChars)}.map(function(c){ return m(c, 'skin'); });
    G.dealerMelds = ${JSON.stringify(meldChars)}.map(function(ch){
      return {type:'zhao', char:ch, count:4, cards:[m(ch,'skin'),m(ch,'skin'),m(ch,'skin'),m(ch,'skin')]};
    });
    G.drawnCard = m(${JSON.stringify(drawChar)}, 'skin');
    G.gameOver = false;
    G._fanChars = []; G._fanPick = null;
    checkDealerZhaAndHu();
    return { fanChars: (G._fanChars||[]).slice(), fanPick: G._fanPick };
  })()`, vmctx);
}

// ── ① 单候选 ──
{
  const r = setup(['礼', '化'], ['可', '知', '二', '四'], '礼');
  check('单候选：_fanChars 只有「礼」', r.fanChars.length === 1 && r.fanChars[0] === '礼', JSON.stringify(r.fanChars));
  const btn = els['btn-fan'];
  check('单候选：泛按钮显示且文案为「泛」', !!btn && btn.style.display !== 'none' && btn.textContent === '泛', btn ? btn.textContent : '无按钮');
}

// ── ② 多候选：手牌同时有礼和化 → 两个招牌都能泛 ──
{
  const r = setup(['礼', '化'], ['礼', '化', '可', '知'], '化');
  check('多候选：_fanChars 同时包含「礼」「化」',
    r.fanChars.length === 2 && r.fanChars.indexOf('礼') >= 0 && r.fanChars.indexOf('化') >= 0,
    JSON.stringify(r.fanChars));
  const btn = els['btn-fan'];
  check('多候选：泛按钮文案带出候选（泛(礼/化)）', !!btn && /礼/.test(btn.textContent) && /化/.test(btn.textContent), btn ? btn.textContent : '无按钮');
  // 点击按钮 → 应弹选择框，而不是直接执行泛牌
  let opened = 0;
  const origCreate = ctx.document.createElement;
  btn.onclick();
  opened = rec.created.filter(e => String(e.id || '').indexOf('fan-pick') >= 0).length;
  check('多候选：点击泛按钮弹出选择框（未直接执行）', opened > 0, `新建元素 ${rec.created.length} 个`);
}

// ── ③ 选择后按所选字执行：dealerFan('化') 不应再询问 ──
{
  setup(['礼', '化'], ['礼', '化', '可', '知'], '化');
  const r = vm.runInContext(`(function(){
    G._fanPick = null;
    var opened = 0;
    var origDialog = (typeof showFanPickDialog === 'function') ? showFanPickDialog : null;
    if (origDialog) showFanPickDialog = function(){ opened++; };
    try { dealerFan('化'); } catch(e) { /* 沙箱 DOM 有限，后续渲染可能抛错，不影响判定层断言 */ }
    if (origDialog) showFanPickDialog = origDialog;
    return { pick: G._fanPick, dialogOpened: opened,
             meldTypes: (G.dealerMelds||[]).map(function(m){ return m.type + ':' + (m.char||''); }) };
  })()`, vmctx);
  check('选择后：记录玩家所选字（G._fanPick = 化）', r.pick === '化', JSON.stringify(r.pick));
  check('选择后：不再二次弹选择框（直接执行）', r.dialogOpened === 0, `弹框次数 ${r.dialogOpened}`);
}

console.log('\n────────────────────────');
console.log(`结果: 通过 ${pass} / 失败 ${fail}`);
process.exit(fail === 0 ? 0 : 1);
