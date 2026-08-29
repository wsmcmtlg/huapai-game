// 用户场景单测：穿牌(七柒七七赖)+口眼(柒土) 应重分配为 穿牌(七七柒柒赖)+口眼(七土) => 70胡 -> 84胡
const fs = require('fs')
const path = require('path');;
const vm = require('vm');

function runScenario(corePath, label) {
  const core = fs.readFileSync(corePath, 'utf8');
  const sandbox = { console, Set, Object, Array, Math, Number, String, Date, JSON, parseInt, parseFloat, Infinity, NaN };
  vm.createContext(sandbox);
  // 拼接 core + test 在同一 runInContext 中执行（顶层 const 不挂 globalThis，必须同域）
  const testCode = `
(function() {
  const mk = makeCardData;
  const preMelds = [
    {type:'chuan', chars:['七','七','七','七','赖'], cards:[mk('七','skin'), mk('七','flower'), mk('七','skin'), mk('七','skin'), mk('赖')]},
    {type:'zha',  chars:['土','土','土','土'], cards:[mk('土'),mk('土'),mk('土'),mk('土')]},
    {type:'zhao', chars:['上','上','上','上'], cards:[mk('上'),mk('上'),mk('上'),mk('上')]},
    {type:'pen',  chars:['化','化','化'], cards:[mk('化'),mk('化'),mk('化')]},
  ];
  const cards = [
    mk('七','flower'), mk('土'),                       // 口眼(柒土)
    mk('可'), mk('知'), mk('礼'),                      // 顺子 可知礼
    mk('三','skin'), mk('四'), mk('五','flower'),       // 顺子 三四伍
    mk('八'), mk('九','skin'), mk('子'),               // 顺子 八九子
    mk('八'), mk('九','skin'), mk('十'),               // 顺子 八九十
  ];
  const r = analyzeHand(cards, preMelds);
  if (!r) return {isWin:false};
  const det = _calcTotalHu(r.melds, r.mainJin);
  return {
    isWin: r.isWin, totalHu: det.total, mainJin: r.mainJin,
    breakdown: det.breakdown.map(b => b.label + '(' + b.chars + ')=' + b.hu).join(' | ')
  };
})()
`;
  const result = vm.runInContext(core + '\n' + testCode, sandbox);
  console.log('==== ' + label + ' ====');
  console.log(JSON.stringify(result, null, 2));
  return result;
}

const before = runScenario(path.join(__dirname, 'hu_tests', 'hu_core_before.js'), '修复前（备份版）');
const after = runScenario(path.join(__dirname, 'hu_tests', 'hu_core_current.js'), '修复后（当前版）');

console.log('\n==== 对比 ====');
console.log('修复前 totalHu =', before.totalHu, '  => 期望 70');
console.log('修复后 totalHu =', after.totalHu, '  => 期望 84');
console.log('修复结果:', before.totalHu === 70 && after.totalHu === 84 ? '✅ PASS' : '❌ FAIL');
