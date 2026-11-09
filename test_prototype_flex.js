// ═══════════════════════════════════════════════════════════
// test_prototype_flex.js — 扎/穿席位可重选 + 赖再分配 的牌型级验收（2026-11-06）
//
// 原型（用户给）：上上上上 可可可可 乙二三 四五六 八九子 七十土 化三千 三叁叁赖赖
//   花精 = 壹叁伍柒玖（大写）／皮精 = 乙三五七九（小写）
//   扎了三次；因扎/穿在玩家手中、旁家未知，只要满足扎数量，具体哪几张扎、赖怎么分都由玩家自主
//
// 验收目标（用户口径）：
//   ① 捉铳 22 个字全部可胡
//   ② 胡上 / 胡可 = 108 胡；胡化 / 胡千 = 64 胡
// ═══════════════════════════════════════════════════════════
'use strict';
const vm = require('vm');
const { loadGameCode, buildSandbox } = require('./measure_winrate.js');

const ALL22 = '上大人可知礼化三千孔乙己二四五六七八九十子土'.split('');
let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log('✅ ' + name + (detail ? '  ' + detail : '')); }
  else { fail++; console.log('❌ ' + name + (detail ? '  ' + detail : '')); }
}

const loader = loadGameCode();
const { vmctx } = buildSandbox(20261106);
vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
for (const c of loader.chunks) { try { vm.runInContext(c, vmctx); } catch (e) {} }

const res = vm.runInContext(`(function(){
  var m = makeCardData;
  G.dealerMelds = [
    {type:'zha', char:'上', count:4, inHand:true, cards:[m('上','skin'),m('上','skin'),m('上','skin'),m('上','skin')]},
    {type:'zha', char:'可', count:4, inHand:true, cards:[m('可','skin'),m('可','skin'),m('可','skin'),m('可','skin')]},
    {type:'zha', char:'三', count:4, inHand:true, isWildZha:true,
     cards:[m('三','flower'),m('三','flower'),m('赖'),m('赖')]}
  ];
  // 手牌：乙二三 四五六 八九子 七十土 化三千 + 1 张皮三（精牌一律皮=小写，与用户写法一致）
  handCards = '乙二三四五六八九子七十土化三千三'.split('').map(function(ch){ return m(ch,'skin'); });
  var out = {};
  ${JSON.stringify(ALL22)}.forEach(function(t){
    var cards = handCards.slice();
    cards.push(Object.assign(m(t), {isTongCard: true}));
    var best = _huFlexPick(cards, G.dealerMelds);
    out[t] = best ? best.totalHu : 0;
  });
  return out;
})()`, vmctx);

const win = ALL22.filter(t => res[t] > 0);
const lose = ALL22.filter(t => !res[t]);
check('捉铳 22 字全部可胡', lose.length === 0, `能胡 ${win.length}/22${lose.length ? ' 缺:' + lose.join(' ') : ''}`);
check('胡上 = 108 胡', res['上'] === 108, `实际 ${res['上']}`);
check('胡可 = 108 胡', res['可'] === 108, `实际 ${res['可']}`);
check('胡化 = 64 胡', res['化'] === 64, `实际 ${res['化']}`);
check('胡千 = 64 胡', res['千'] === 64, `实际 ${res['千']}`);
check('胡知 = 108 胡（可知礼组与上大人同构）', res['知'] === 108, `实际 ${res['知']}`);

console.log('\n────────────────────────');
console.log(`结果: 通过 ${pass} / 失败 ${fail}`);
process.exit(fail === 0 ? 0 : 1);
