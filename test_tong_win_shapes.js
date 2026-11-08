// ═══════════════════════════════════════════════════════════
// test_tong_win_shapes.js — 牌型级回归：吃统=捉铳的两种典型形态（2026-11-05）
//
// 规则依据（用户 2026-11-05）：
//   "吃必须捉铳"与"统牌只能凑碰或顺"是同一件事：唯一条件是吃进这张牌即满足胡牌。
//   统牌可凑顺、可凑碰、也可在摞听时配赖做眼。
//
// 用例1（两听口）：上上上 大大大 可知 二三四 五五五 六七八 七十土 化三千 孔孔
//   · 捉铳「礼」→ 可知礼 凑顺，孔孔 做眼
//   · 捉铳「孔」→ 孔孔孔 凑碰，可知 做口眼
// 用例2（摞听赖）：上上上 大大大 可知礼 二三四 [五五五五=扎] 六七八 七十土 化三千 赖
//   · 能胡：化 三 千 乙 二 四 五 六 七 八 九 十 子 土（14 字）
//   · 不能胡：上 大 人 可 知 礼 孔 己（上大人可知礼 / 孔乙己 两个顺子的成员）
//
// 这两条是"牌型级"护栏：谁动了 _partition / 赖子逻辑 / 统牌 isTongCard 处理，
// 一跑就知道有没有破。
// ═══════════════════════════════════════════════════════════
'use strict';
const vm = require('vm');
const { loadGameCode, buildSandbox } = require('./measure_winrate.js');

let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log('✅ ' + name + (detail ? '  ' + detail : '')); }
  else { fail++; console.log('❌ ' + name + (detail ? '  ' + detail : '')); }
}

const ALL22 = '上大人可知礼化三千孔乙己二四五六七八九十子土'.split('');
const loader = loadGameCode();

function freshSandbox() {
  const { vmctx } = buildSandbox(20261105);
  vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
  for (const chunk of loader.chunks) { try { vm.runInContext(chunk, vmctx); } catch (e) {} }
  return vmctx;
}

// 对"手牌 + 统牌"跑 analyzeHand，返回 {isWin, hu, melds:[type(chars)]}
function tongWin(vmctx, handChars, tongChar, preMelds) {
  return vm.runInContext(`(function(){
    var cards = ${JSON.stringify(handChars)}.map(function(c){ return makeCardData(c); });
    cards.push(Object.assign(makeCardData(${JSON.stringify(tongChar)}), {isTongCard: true}));
    var r = analyzeHand(cards, ${JSON.stringify(preMelds || [])}.map(function(m){
      var cs = m.cards.map(function(c){ return makeCardData(c); });
      return {type: m.type, chars: cs.map(function(c){return c.ch;}), cards: cs, inHand: !!m.inHand};
    }));
    if (!r) return {isWin: false, hu: 0, melds: []};
    return {isWin: !!r.isWin, hu: r.totalHu || 0,
            melds: (r.melds||[]).map(function(m){ return m.type + '(' + (m.chars||[]).join('') + ')'; })};
  })()`, vmctx);
}

// ── 用例1：两听口（凑顺 / 凑碰）──
{
  const vmctx = freshSandbox();
  const hand = '上上上大大大可知二三四五五五六七八七十土化三千孔孔'.split('');
  check('用例1 手牌 25 张', hand.length === 25, `实际=${hand.length}`);

  const rLi = tongWin(vmctx, hand, '礼');
  check('用例1 捉铳「礼」→ 胡（可知礼凑顺）', rLi.isWin,
    `hu=${rLi.hu} 分解=${rLi.melds.join(' ')}`);
  check('用例1 「礼」分解含顺子(可知礼) 与 眼(孔孔)',
    rLi.melds.includes('seq(可知礼)') && rLi.melds.some(m => /pair|kou/.test(m)),
    rLi.melds.join(' '));

  const rKong = tongWin(vmctx, hand, '孔');
  check('用例1 捉铳「孔」→ 胡（孔孔孔凑碰、可知做口眼）', rKong.isWin,
    `hu=${rKong.hu} 分解=${rKong.melds.join(' ')}`);
  check('用例1 「孔」分解含碰(孔孔孔) 且不含坎(孔孔孔)',
    rKong.melds.includes('pen(孔孔孔)') && !rKong.melds.includes('kan(孔孔孔)'),
    rKong.melds.join(' '));
}

// ── 用例2：摞听赖（赖只通配精牌三五七）──
{
  const vmctx = freshSandbox();
  const hand = '上上上大大大可知礼二三四六七八七十土化三千赖'.split('');
  const zhaMeld = [{ type: 'zha', inHand: true, cards: ['五', '五', '五', '五'] }];
  check('用例2 手牌 22 张 + 扎 4 张', hand.length === 22, `实际=${hand.length}`);

  const expectWin = '化三千乙二四五六七八九十子土'.split('');
  const expectLose = '上大人可知礼孔己'.split('');

  const gotWin = [], gotLose = [];
  const huLog = [];
  for (const t of ALL22) {
    const r = tongWin(vmctx, hand, t, zhaMeld);
    if (r.isWin) { gotWin.push(t); huLog.push(t + ':' + r.hu); } else gotLose.push(t);
  }
  check('用例2 能胡的字集合正确（14 字）',
    gotWin.join('') === expectWin.join(''),
    `实际能胡=${gotWin.join(' ')}`);
  check('用例2 不能胡的字集合正确（上大人可知礼孔己）',
    gotLose.join('') === expectLose.join(''),
    `实际不能胡=${gotLose.join(' ')}`);
  check('用例2 胡数都在 30 以上（成形即远超 17 胡门槛）',
    huLog.every(x => +x.split(':')[1] >= 30), huLog.join(' '));
}

console.log('\n────────────────────────');
console.log(`结果: 通过 ${pass} / 失败 ${fail}`);
process.exit(fail === 0 ? 0 : 1);
