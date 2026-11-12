// ═══════════════════════════════════════════════════════════
// test_hu_structure.js — 两条"原则性规则"回归（2026-11-06）
//
// 规则（用户实测发现被违反）：
//   ① 赖子只能通配精牌三五七，不能配「人」等非精字 → 不许用赖把「人」凑成扎/穿
//   ② 胡牌结构必须是「8 圆句 + 1 眼」→ 7 圆句 + 1 眼（7+2）不算胡
//
// 本测试直接验证 _huFlexPick 的判定边界。
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
const { ctx, vmctx } = buildSandbox(202611120);
vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
for (const c of loader.chunks) { try { vm.runInContext(c, vmctx); } catch (e) {} }

// ── 用例①：赖子配「人」凑穿牌 —— 必须不成立 ──
{
  const r = vm.runInContext(`(function(){
    var m = makeCardData;
    // 手中 3 张「人」+ 2 张赖；若规则被违反，会拼出「穿(人人人赖赖)」
    var hand = ['人','人','人','赖','赖','上','大','二','四','六','八','十','子','土','可','知','礼','千','化','三','五','七','乙','九'].map(function(c){ return m(c,'skin'); });
    var melds = [];
    var best = _huFlexPick(hand, melds);
    var hasRenChuan = false;
    if (best && best.result && best.result.melds) {
      best.result.melds.forEach(function(mm){
        if (mm.type === 'chuan' && (mm.chars || []).indexOf('人') >= 0) hasRenChuan = true;
      });
    }
    return { hasRenChuan: hasRenChuan, hu: best ? best.totalHu : null };
  })()`, vmctx);
  check('赖子不能配非精字「人」凑穿牌', r.hasRenChuan === false, `结果 ${JSON.stringify(r)}`);
}

// ── 用例②：7 圆句 + 1 眼（7+2）不得判胡 ──
{
  const r = vm.runInContext(`(function(){
    var m = makeCardData;
    // 7 组牌型 + 1 眼 = 23 张，标准 8+1 差一组 —— 必须不胡
    var chars = '上上上大大大 可知礼 二三四 五五五 六七八 七十土 孔孔'.replace(/ /g,'').split('');
    var hand = chars.map(function(c){ return m(c,'skin'); });
    var best = _huFlexPick(hand, []);
    return { hu: best ? best.totalHu : null, melds: best && best.result ? best.result.melds.length : 0 };
  })()`, vmctx);
  check('7 圆句 + 1 眼（23 张）不判胡', r.hu === null, `结果 ${JSON.stringify(r)}`);
}

// ── 用例③：8 圆句 + 1 眼（26 张）应当判胡（对照组，确保没把正常胡也挡掉）──
{
  const r = vm.runInContext(`(function(){
    var m = makeCardData;
    var chars = '上上上大大大可知礼二三四五五五六七八七十土化三千孔孔'.split('');
    var hand = chars.map(function(c){ return m(c,'skin'); });
    var best = _huFlexPick(hand, []);
    return { hu: best ? best.totalHu : null, melds: best && best.result ? best.result.melds.length : 0 };
  })()`, vmctx);
  check('8 圆句 + 1 眼（26 张）正常判胡', r.hu !== null && r.hu > 0, `结果 ${JSON.stringify(r)}`);
}

console.log('\n────────────────────────');
console.log(`结果: 通过 ${pass} / 失败 ${fail}`);
process.exit(fail === 0 ? 0 : 1);
