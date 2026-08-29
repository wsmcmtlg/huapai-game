// 回归测试：验证新增"同字花皮重分配"不破坏正常局，且能正确处理各场景
const fs = require('fs')
const path = require('path');;
const vm = require('vm');

// 返回一个每次独立 sandbox 的评估器（顶层 const 声明环境持久化会导致重复声明，故每次新建 sandbox 并拼接 core）
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

function makeScenario(parts) {
  // parts: {preMelds: [meld对象数组], cards: [ch:v 描述字符串数组]}
  // 返回 {preMelds, cards} 可直接嵌入代码
  return parts;
}

function runBoth(desc, scenario) {
  const code = `
    const mk = makeCardData;
    const preMelds = ${JSON.stringify(scenario.preMelds).replace(/"mk\(([^)]*)\)"/g, 'mk($1)')};
    const cards = ${JSON.stringify(scenario.cards.map(mk)).replace(/"mk\(([^)]*)\)"/g, 'mk($1)')};
    const r = analyzeHand(cards, preMelds);
    if (!r) return {isWin:false};
    const det = _calcTotalHu(r.melds, r.mainJin);
    return {isWin:r.isWin, totalHu:det.total, mainJin:r.mainJin,
      breakdown:det.breakdown.map(b=>b.label+'('+b.chars+')='+b.hu).join(' | ')}`;
  const before = beforeEval(code);
  const after = afterEval(code);
  console.log('\n## ' + desc);
  console.log('修复前:', before.isWin ? before.totalHu + '胡' : '不胡', before.isWin ? ' [' + before.breakdown + ']' : '');
  console.log('修复后:', after.isWin ? after.totalHu + '胡' : '不胡', after.isWin ? ' [' + after.breakdown + ']' : '');
  return { before, after };
}

// 辅助：构造 meld 对象
// 用字符串描述牌，如 '七:s'=皮七, '七:f'=花七, '赖'=赖子, '土'=土皮
function mk(desc) {
  const [ch, v] = desc.split(':');
  if (ch === '赖') return `mk('赖')`;
  return v ? `mk('${ch}','${v === 'f' ? 'flower' : 'skin'}')` : `mk('${ch}')`;
}
function meld(type, cardDescs) {
  return { type, chars: cardDescs.map(d => d.split(':')[0]), cards: cardDescs.map(mk) };
}

const commonOther = ['可', '知', '礼', '三:s', '四', '五:f', '八', '九:s', '子', '八', '九:s', '十'];

// ═══ 用例1：用户场景（穿牌次优+口眼花牌） 期望 70 → 84 ═══
{
  const preMelds = [
    meld('chuan', ['七:s', '七:f', '七:s', '七:s', '赖']),
    meld('zha', ['土', '土', '土', '土']),
    meld('zhao', ['上', '上', '上', '上']),
    meld('pen', ['化', '化', '化']),
  ];
  const cards = ['七:f', '土', ...commonOther];
  const r = runBoth('用例1 用户场景(穿牌1花3皮1赖+口眼柒土)', { preMelds, cards });
  const ok = r.before.isWin && r.before.totalHu === 70 && r.after.isWin && r.after.totalHu === 84;
  console.log('  断言: 70 -> 84', ok ? '✅' : '❌ FAIL');
}

// ═══ 用例2：穿牌已最优(2花2皮1赖)，手牌只有皮七 期望前后一致 = 84 ═══
{
  const preMelds = [
    meld('chuan', ['七:s', '七:f', '七:f', '七:s', '赖']),
    meld('zha', ['土', '土', '土', '土']),
    meld('zhao', ['上', '上', '上', '上']),
    meld('pen', ['化', '化', '化']),
  ];
  const cards = ['七:s', '土', ...commonOther];
  const r = runBoth('用例2 穿牌已最优(2花2皮1赖)+手牌皮七', { preMelds, cards });
  const ok = r.before.isWin && r.after.isWin && r.before.totalHu === 84 && r.after.totalHu === 84;
  console.log('  断言: 前后均 84（不劣化）', ok ? '✅' : '❌ FAIL');
}

// ═══ 用例3：手牌完全无同字，不触发重分配 期望前后一致 = 66 ═══
{
  const preMelds = [
    meld('chuan', ['七:s', '七:f', '七:s', '七:s', '赖']),
    meld('zha', ['土', '土', '土', '土']),
    meld('zhao', ['上', '上', '上', '上']),
    meld('pen', ['化', '化', '化']),
  ];
  const cards = ['十', '土', '可', '知', '礼', '三:s', '四', '五:f', '八', '九:s', '子', '八', '九:s', '十'];
  const r = runBoth('用例3 手牌无同字七(穿牌无法重分配)', { preMelds, cards });
  const ok = r.before.isWin && r.after.isWin && r.before.totalHu === 66 && r.after.totalHu === 66;
  console.log('  断言: 前后均 66（无交换空间不误改）', ok ? '✅' : '❌ FAIL');
}

// ═══ 用例4：扎牌花皮重分配 期望 40 → 46 ═══
{
  const preMelds = [
    meld('zha', ['七:f', '七:s', '七:s', '赖']),
    meld('zhao', ['上', '上', '上', '上']),
    meld('pen', ['化', '化', '化']),
  ];
  const cards = ['七:f', '土', ...commonOther];
  const r = runBoth('用例4 扎牌(1花2皮1赖)+手牌花七', { preMelds, cards });
  const ok = r.before.isWin && r.before.totalHu === 40 && r.after.isWin && r.after.totalHu === 46;
  console.log('  断言: 40 -> 46（扎牌重分配）', ok ? '✅' : '❌ FAIL');
}

// ═══ 用例5：普通纯自由牌胡牌（无扩展牌型），修复前后应完全一致 ═══
{
  // 旁家25张: 口眼(柒土) + 顺子可知礼 + 三四伍 + 八九子 + 八九十 + 坎七(七柒柒)+坎伍(伍伍伍)
  // 构造: 1眼(2) + 5型牌(顺子4*3 + 坎3) = 2 + 15 = 17 手牌? 需要7型+2眼=25
  // 简化用单眼+多型牌结构验证一致性即可
  const preMelds = [];
  // 手牌17张 = 1眼2 + 5组型牌15；再加一组眼? 不够，直接构造任意合法局
  const cards = ['七:f', '土', '可', '知', '礼', '三:s', '四', '五:f', '八', '九:s', '子', '八', '九:s', '十'];
  const r = runBoth('用例5 无扩展牌型(仅自由牌14张=1眼+4顺子)', { preMelds, cards });
  const ok = r.before.isWin === r.after.isWin && (!r.before.isWin || r.before.totalHu === r.after.totalHu);
  console.log('  断言: 前后一致', ok ? '✅' : '❌ FAIL');
}

console.log('\n全部回归用例执行完毕');
