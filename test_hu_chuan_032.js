// 本局单测：穿牌(七七七赖赖)=0花3皮2赖 缺查表条目'0_3_2'，应计56胡(主精)，总胡 41 → 67
// 同时回归验证第一局(穿牌花皮重分配 70→84) 仍有效
const fs = require('fs')
const path = require('path');;
const vm = require('vm');

function makeEval(corePath) {
  const core = fs.readFileSync(corePath, 'utf8');
  return function(code) {
    const sandbox = { console, Set, Object, Array, Math, Number, String, Date, JSON, parseInt, parseFloat, Infinity, NaN };
    vm.createContext(sandbox);
    return JSON.parse(vm.runInContext(core + '\n' + 'JSON.stringify((function(){' + code + '})())', sandbox));
  };
}
const beforeEval = makeEval(path.join(__dirname, 'hu_tests', 'hu_core_before.js'));
const afterEval = makeEval(path.join(__dirname, 'hu_tests', 'hu_core_current.js'));

function run(evalFn, code) { return evalFn(code); }

// ═══ 本局：穿牌(七七七赖赖) 0花3皮2赖，应 30→56，总 41→67 ═══
const scenario2 = `
  const mk = makeCardData;
  const preMelds = [
    {type:'chuan', chars:['七','七','七','赖','赖'], cards:[mk('七','skin'),mk('七','skin'),mk('七','skin'),mk('赖'),mk('赖')]},
    {type:'zhao', chars:['四','四','四','四'], cards:[mk('四'),mk('四'),mk('四'),mk('四')]},
    {type:'pen',  chars:['二','二','二'], cards:[mk('二'),mk('二'),mk('二')]},
    {type:'pen',  chars:['人','人','人'], cards:[mk('人'),mk('人'),mk('人')]}
  ];
  const cards = [
    mk('五','flower'), mk('五','skin'),
    mk('礼'), mk('礼'), mk('礼'),
    mk('孔'), mk('乙','flower'), mk('己'),
    mk('八'), mk('九','flower'), mk('子'),
    mk('八'), mk('九','flower'), mk('十')
  ];
  const r = analyzeHand(cards, preMelds);
  if (!r) return {isWin:false};
  const det = _calcTotalHu(r.melds, r.mainJin);
  return {isWin:r.isWin, totalHu:det.total, mainJin:r.mainJin,
    breakdown:det.breakdown.map(b=>b.label+'('+b.chars+')='+b.hu).join(' | ')}`;

console.log('==== 本局：穿牌(七七七赖赖) ====');
const b2 = run(beforeEval, scenario2);
const a2 = run(afterEval, scenario2);
console.log('修复前:', b2.isWin ? b2.totalHu + '胡 [' + b2.breakdown + ']' : '不胡');
console.log('修复后:', a2.isWin ? a2.totalHu + '胡 [' + a2.breakdown + ']' : '不胡');
const ok2 = b2.isWin && b2.totalHu === 41 && a2.isWin && a2.totalHu === 67;
console.log('断言: 41 -> 67', ok2 ? '✅' : '❌ FAIL');

// ═══ 回归：第一局 穿牌花皮重分配 70 → 84 ═══
const scenario1 = `
  const mk = makeCardData;
  const preMelds = [
    {type:'chuan', chars:['七','七','七','七','赖'], cards:[mk('七','skin'), mk('七','flower'), mk('七','skin'), mk('七','skin'), mk('赖')]},
    {type:'zha',  chars:['土','土','土','土'], cards:[mk('土'),mk('土'),mk('土'),mk('土')]},
    {type:'zhao', chars:['上','上','上','上'], cards:[mk('上'),mk('上'),mk('上'),mk('上')]},
    {type:'pen',  chars:['化','化','化'], cards:[mk('化'),mk('化'),mk('化')]}
  ];
  const cards = [
    mk('七','flower'), mk('土'),
    mk('可'), mk('知'), mk('礼'),
    mk('三','skin'), mk('四'), mk('五','flower'),
    mk('八'), mk('九','skin'), mk('子'),
    mk('八'), mk('九','skin'), mk('十')
  ];
  const r = analyzeHand(cards, preMelds);
  if (!r) return {isWin:false};
  const det = _calcTotalHu(r.melds, r.mainJin);
  return {isWin:r.isWin, totalHu:det.total, mainJin:r.mainJin}`;

console.log('\n==== 回归：第一局 穿牌花皮重分配 ====');
const b1 = run(beforeEval, scenario1);
const a1 = run(afterEval, scenario1);
console.log('修复前:', b1.isWin ? b1.totalHu + '胡' : '不胡', ' 修复后:', a1.isWin ? a1.totalHu + '胡' : '不胡');
const ok1 = b1.isWin && b1.totalHu === 70 && a1.isWin && a1.totalHu === 84;
console.log('断言: 70 -> 84（回归）', ok1 ? '✅' : '❌ FAIL');

console.log('\n结果:', ok2 && ok1 ? '全部通过 ✅' : '有失败 ❌');
