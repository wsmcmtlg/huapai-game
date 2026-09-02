// ═══════════════════════════════════════════════════════
// Phase 7 单测：AI 期望损失（"两害相权取其轻"）
// 覆盖：
//   场景A: A明牌20胡 vs B明牌5胡，同一危险字ch，riskCost 分家加权正确
//   场景B: 某ch只被A需要 vs 只被B需要，加权求和正确
//   场景C: estPoints 阶梯映射正确（17→3、22→4、27→5；<17按比例）
// ═══════════════════════════════════════════════════════
const fs = require('fs')
const path = require('path');;
const vm = require('vm');

const html = fs.readFileSync(path.join(__dirname, 'step5-hu.html'), 'utf8');
const core = fs.readFileSync(path.join(__dirname, 'hu_tests', 'hu_core_current.js'), 'utf8');

// ── 从 step5-hu.html 按锚点+大括号配平提取函数体 ──
function extractFunction(source, fnAnchor) {
  const start = source.indexOf(fnAnchor);
  if (start < 0) throw new Error('函数锚点未找到: ' + fnAnchor);
  // 找到第一个 '{'（函数体起点）
  const braceStart = source.indexOf('{', start);
  if (braceStart < 0) throw new Error('函数体起点未找到: ' + fnAnchor);
  let depth = 0, i = braceStart;
  for (; i < source.length; i++) {
    const c = source[i];
    if (c === '{') depth++;
    else if (c === '}') { depth--; if (depth === 0) { i++; break; } }
  }
  return source.slice(start, i);
}

// 需要提取的函数（新函数 + 其直接依赖）
const funcs = [];
funcs.push(extractFunction(html, 'function calcMeldHu(m) {'));       // 明牌单副胡数
funcs.push(extractFunction(html, 'function calcMeldHuTotal(pi) {')); // 明牌区胡数合计
funcs.push(extractFunction(html, 'function _huTier(hu) {'));         // 胡数档位
funcs.push(extractFunction(html, 'function calcPoints(hu) {'));      // 计分阶梯
funcs.push('var _aiHuEstCache = { 1: {sig:\'\', hu:null}, 2: {sig:\'\', hu:null} };');  // 估算缓存声明
funcs.push(extractFunction(html, 'function _aiEstimateOpponentHu(pi) {'));  // 预期胡数估算
funcs.push(extractFunction(html, 'function getRiskCost(ch) {'));     // 期望损失评分

// ── 测试代码：在 vm 沙箱中运行 ──
// 依赖桩：opponentHands / opponentMelds / G / getRemainingCount / guessOpponentTing / _aiBehaviorBasedTingGuess
const stubCode = `
// ── 环境桩（每个用例前由测试代码重置） ──
var _stub = {
  opponentHands: { 1: [], 2: [] },
  opponentMelds: { 1: [], 2: [] },
  G: { _passRecord: {}, mainJin: '三' },
  remainMap: {},
  tingGuess: { 1: [], 2: [] },
  behaviorGuess: { 1: [], 2: [] }
};
// 全局引用（新函数直接读这些全局）
var opponentHands = _stub.opponentHands;
var opponentMelds = _stub.opponentMelds;
var G = _stub.G;
function getRemainingCount(ch) { return _stub.remainMap[ch] !== undefined ? _stub.remainMap[ch] : 3; }
function guessOpponentTing(pi) { return _stub.tingGuess[pi] || []; }
function _aiBehaviorBasedTingGuess(pi) { return _stub.behaviorGuess[pi] || []; }
function _aiInitOppBehavior() {}
function _aiAnalyzeOppBehavior(pi) { return { isAggressive: false, handLen: _stub.opponentHands[pi].length, recentDiscardChars: [], unwantedChars: {}, wantedChars: {} }; }
`;

// 测试用例结果收集
const results = [];
function testCase(desc, pass, detail) {
  results.push({ desc, pass, detail });
  console.log('  ' + (pass ? '✅' : '❌') + ' ' + desc + (detail ? '  [' + detail + ']' : ''));
}

function runCase(code) {
  const sandbox = { console, Set, Object, Array, Math, Number, String, Date, JSON, parseInt, parseFloat, Infinity, NaN, require };
  vm.createContext(sandbox);
  return JSON.parse(vm.runInContext(core + '\n' + funcs.join('\n') + '\n' + stubCode + '\n' + 'JSON.stringify((function(){' + code + '})())', sandbox));
}

// ═══ 场景A：明牌20胡 vs 明牌5胡，同一危险字 → 分家加权 ═══
{
  // A(pi=1)：明牌区构造约20胡（用穿牌8胡×2 + 碰红1胡×2 + 坎…近似，实际以calcMeldHuTotal为准）
  // 简化：直接用 meld 数组构造，断言 estHu 反映 meldHu 差异
  const r = runCase(`
    // A家明牌：2个红碰(2胡) + 1个穿牌(基础8胡) ≈ 10+ ；B家明牌：1个黑碰(0胡)
    _stub.opponentMelds[1] = [
      {type:'pen', cards:[{ch:'三',v:'skin'},{ch:'三',v:'skin'},{ch:'三',v:'skin'}]},
      {type:'pen', cards:[{ch:'五',v:'skin'},{ch:'五',v:'skin'},{ch:'五',v:'skin'}]},
      {type:'chuan', cards:[{ch:'七',v:'skin'},{ch:'七',v:'skin'},{ch:'七',v:'skin'},{ch:'七',v:'flower'},{ch:'七',v:'skin'}]}
    ];
    _stub.opponentMelds[2] = [
      {type:'pen', cards:[{ch:'乙',v:'skin'},{ch:'乙',v:'skin'},{ch:'乙',v:'skin'}]}
    ];
    _stub.opponentHands[1] = ['上','大','人','可','知'];
    _stub.opponentHands[2] = ['化','三','五','七','赖'];
    _aiHuEstCache = { 1: {sig:'', hu:null}, 2: {sig:'', hu:null} };
    var e1 = _aiEstimateOpponentHu(1);
    var e2 = _aiEstimateOpponentHu(2);
    return {e1meld:e1.meldHu, e2meld:e2.meldHu, e1hu:e1.estHu, e2hu:e2.estHu, e1p:e1.estPoints, e2p:e2.estPoints};
  `);
  console.log('## 场景A 明牌20胡 vs 5胡（meldHu=实际明牌胡数）');
  testCase('A家明牌胡数 > B家', r.e1meld > r.e2meld, 'A=' + r.e1meld + ' B=' + r.e2meld);
  testCase('A家estHu > B家estHu', r.e1hu > r.e2hu, 'A=' + r.e1hu + ' B=' + r.e2hu);
  testCase('A家estPoints >= B家estPoints', r.e1p >= r.e2p, 'A=' + r.e1p + ' B=' + r.e2p);
  // 断言A明牌胡数确实超过B（构造应满足）
  testCase('构造校验: A明牌 > B明牌', r.e1meld > r.e2meld, '');
}

// ═══ 场景B：同一ch只被A需要 vs 只被B需要 → 加权求和正确 ═══
{
  const r = runCase(`
    // 两家手牌相同牌力，但听牌推测不同：ch='上' 只被A(高胡)需要，ch='化' 只被B(低胡)需要
    _stub.opponentMelds[1] = [
      {type:'chuan', cards:[{ch:'七',v:'skin'},{ch:'七',v:'skin'},{ch:'七',v:'skin'},{ch:'七',v:'flower'},{ch:'七',v:'skin'}]},
      {type:'pen', cards:[{ch:'三',v:'skin'},{ch:'三',v:'skin'},{ch:'三',v:'skin'}]}
    ];
    _stub.opponentMelds[2] = [
      {type:'pen', cards:[{ch:'乙',v:'skin'},{ch:'乙',v:'skin'},{ch:'乙',v:'skin'}]}
    ];
    _stub.opponentHands[1] = ['上','大','人','可','知'];
    _stub.opponentHands[2] = ['化','千','三','五','赖'];
    _stub.tingGuess[1] = [{ch:'上', c:0.8}];   // A需要'上'
    _stub.tingGuess[2] = [{ch:'化', c:0.8}];   // B需要'化'
    _stub.remainMap['上'] = 2; _stub.remainMap['化'] = 2;
    _stub.G._passRecord = {};
    _aiHuEstCache = { 1: {sig:'', hu:null}, 2: {sig:'', hu:null} };
    var riskShang = getRiskCost('上');  // 只有A需要，权重=A的estPoints
    var riskHua = getRiskCost('化');    // 只有B需要，权重=B的estPoints
    var e1 = _aiEstimateOpponentHu(1), e2 = _aiEstimateOpponentHu(2);
    return {riskShang:riskShang, riskHua:riskHua, e1p:e1.estPoints, e2p:e2.estPoints, e1hu:e1.estHu, e2hu:e2.estHu};
  `);
  console.log('## 场景B 分家加权（只被A需要 vs 只被B需要）');
  testCase('A家胡数权重 > B家胡数权重', r.e1hu > r.e2hu, 'A=' + r.e1hu + ' B=' + r.e2hu);
  testCase('喂给A的牌riskCost > 喂给B的牌', r.riskShang > r.riskHua, '上=' + r.riskShang.toFixed(3) + ' 化=' + r.riskHua.toFixed(3));
}

// ═══ 场景C：estPoints 阶梯映射 ═══
{
  const r = runCase(`
    // 直接测 calcPoints 阶梯 + _aiEstimateOpponentHu 的 <17 比例段
    _stub.opponentMelds[1] = [];
    _stub.opponentMelds[2] = [];
    _stub.opponentHands[1] = [];  // estHu=0 → estPoints=0
    _stub.opponentHands[2] = ['三','三','三','赖','赖']; // 红精坎5+2赖*2=9 → estHu=9
    _aiHuEstCache = { 1: {sig:'', hu:null}, 2: {sig:'', hu:null} };
    var c17 = calcPoints(17), c22 = calcPoints(22), c27 = calcPoints(27);
    var eEmpty = _aiEstimateOpponentHu(1);
    var eJing = _aiEstimateOpponentHu(2);
    return {c17:c17, c22:c22, c27:c27, emptyHu:eEmpty.estHu, emptyP:eEmpty.estPoints, jingHu:eJing.estHu, jingP:eJing.estPoints};
  `);
  console.log('## 场景C estPoints 阶梯映射');
  testCase('calcPoints(17)=3', r.c17 === 3, 'got ' + r.c17);
  testCase('calcPoints(22)=4', r.c22 === 4, 'got ' + r.c22);
  testCase('calcPoints(27)=5', r.c27 === 5, 'got ' + r.c27);
  testCase('空手 estPoints=0（无威胁）', r.emptyP === 0, 'estHu=' + r.emptyHu + ' p=' + r.emptyP);
  testCase('红精坎+赖 estHu>0 且 estPoints>0', r.jingHu > 0 && r.jingP > 0, 'estHu=' + r.jingHu + ' p=' + r.jingP.toFixed(2));
  testCase('有牌力 estPoints > 空手', r.jingP > r.emptyP, r.jingP.toFixed(2) + ' vs ' + r.emptyP);
}

// ═══ 汇总 ═══
console.log('\n════════════════════════════════════════');
const passCount = results.filter(r => r.pass).length;
const failCount = results.filter(r => !r.pass).length;
console.log('结果: 通过 ' + passCount + ' / 失败 ' + failCount);
if (failCount === 0) {
  console.log('✅ 全部通过');
} else {
  console.log('❌ 存在失败');
  process.exit(1);
}
