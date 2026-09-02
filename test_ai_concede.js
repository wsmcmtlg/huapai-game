// ═══════════════════════════════════════════════════════
// Phase 7.5 单测：显式止损模式（concede）
// 覆盖：
//   场景A: 弱牌+旁家威胁大+晚局 → concede=true
//   场景B: 强牌（精/赖多）→ 不触发
//   场景C: 弱牌但旁家无威胁 → 不触发
//   场景D: 弱牌+威胁大但余牌多（发展期）→ 不触发
//   场景E: 威胁边界（estPoints 3.5 上下）
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

const funcs = [];
funcs.push(extractFunction(html, 'function calcMeldHu(m) {'));       // 明牌单副胡数
funcs.push(extractFunction(html, 'function calcMeldHuTotal(pi) {')); // 明牌区胡数合计
funcs.push(extractFunction(html, 'function _huTier(hu) {'));         // 胡数档位
funcs.push(extractFunction(html, 'function calcPoints(hu) {'));      // 计分阶梯
funcs.push('var _aiHuEstCache = { 1: {sig:\'\', hu:null}, 2: {sig:\'\', hu:null} };');
funcs.push(extractFunction(html, 'function _aiEstimateOpponentHu(pi) {'));  // 预期胡数
funcs.push(extractFunction(html, 'function _aiGetConcedeMode(playerIdx) {')); // 止损判定

// ── 环境桩 ──
const stubCode = `
var _stub = {
  opponentHands: { 1: [], 2: [] },
  opponentMelds: { 1: [], 2: [] },
  G: { _passRecord: {}, mainJin: '三', deckCount: 30 }
};
var opponentHands = _stub.opponentHands;
var opponentMelds = _stub.opponentMelds;
var G = _stub.G;
// G_CARD_TOTALS 简化版：22字面×5 + 赖2 = 112
var G_CARD_TOTALS = {};
(function(){ var allC = '上大人可知礼化三千孔乙己七十土八九子二四五六七八九十赖'; for (var i=0;i<allC.length;i++) G_CARD_TOTALS[allC[i]] = 5; G_CARD_TOTALS['赖'] = 2; })();
function getRemainingCount(ch) { return 3; }
function guessOpponentTing(pi) { return []; }
function _aiBehaviorBasedTingGuess(pi) { return []; }
function _aiInitOppBehavior() {}
function _aiAnalyzeOppBehavior(pi) { return { isAggressive: false, handLen: _stub.opponentHands[pi].length, recentDiscardChars: [], unwantedChars: {}, wantedChars: {} }; }
`;

const results = [];
function testCase(desc, pass, detail) {
  results.push({ desc, pass, detail });
  console.log('  ' + (pass ? '✅' : '❌') + ' ' + desc + (detail ? '  [' + detail + ']' : ''));
}

function runCase(code) {
  const sandbox = { console, Set, Object, Array, Math, Number, String, Date, JSON, parseInt, parseFloat, Infinity, NaN };
  vm.createContext(sandbox);
  return JSON.parse(vm.runInContext(core + '\n' + funcs.join('\n') + '\n' + stubCode + '\n' + 'JSON.stringify((function(){' + code + '})())', sandbox));
}

// 弱牌（无精/赖/坎，口子少）：'人','礼','千','己','土','子','二','四','六','八'
const WEAK_HAND = `['人','千','己','土','二','四','八']`;
// 强旁家(pi=2)：明牌穿七(2花3皮=28胡非主精) + 手牌红精坎+赖 → estPoints 高
const STRONG_OPP = `
  _stub.opponentMelds[2] = [
    {type:'chuan', cards:[{ch:'七',v:'flower'},{ch:'七',v:'flower'},{ch:'七',v:'skin'},{ch:'七',v:'skin'},{ch:'七',v:'skin'}]}
  ];
  _stub.opponentHands[2] = ['三','三','三','赖','赖'];
  _aiHuEstCache = { 1: {sig:'', hu:null}, 2: {sig:'', hu:null} };
`;

// ═══ 场景A：弱牌 + 旁家威胁大 + 晚局 → concede=true ═══
{
  const r = runCase(`
    _stub.opponentHands[1] = ${WEAK_HAND};   // 自己(playerIdx=1)弱牌
    ${STRONG_OPP}
    G.deckCount = 30;  // 30/112 ≈ 0.27 → 晚局
    var c = _aiGetConcedeMode(1);
    return {concede:c.concede, weak:c.weak, oppThreat:c.oppThreat, lateGame:c.lateGame, maxOppHu:c.maxOppHu, remainRatio:c.remainRatio};
  `);
  console.log('## 场景A 弱牌+威胁大+晚局');
  testCase('concede=true', r.concede === true, JSON.stringify(r));
  testCase('weak=true', r.weak === true, '');
  testCase('oppThreat=true', r.oppThreat === true, 'maxOppHu=' + r.maxOppHu.toFixed(2));
  testCase('lateGame=true', r.lateGame === true, 'ratio=' + r.remainRatio.toFixed(2));
}

// ═══ 场景B：强牌（精/赖多）→ 不触发 ═══
{
  const r = runCase(`
    // 自己手牌强：多红精+赖+坎
    _stub.opponentHands[1] = ['三','三','三','五','赖','七','七','七','上','大'];
    ${STRONG_OPP}
    G.deckCount = 30;
    var c = _aiGetConcedeMode(1);
    return {concede:c.concede, weak:c.weak, jingScore:c.jingScore, kanCount:c.kanCount};
  `);
  console.log('## 场景B 强牌');
  testCase('concede=false', r.concede === false, 'jingScore=' + r.jingScore + ' kan=' + r.kanCount);
  testCase('weak=false', r.weak === false, '');
}

// ═══ 场景C：弱牌但旁家无威胁 → 不触发 ═══
{
  const r = runCase(`
    _stub.opponentHands[1] = ${WEAK_HAND};  // 自己弱
    // 旁家也弱：无精无坎，无明牌胡数
    _stub.opponentMelds[2] = [];
    _stub.opponentHands[2] = ['化','千','孔','己','子','八','九','十','二','四'];
    _aiHuEstCache = { 1: {sig:'', hu:null}, 2: {sig:'', hu:null} };
    G.deckCount = 30;
    var c = _aiGetConcedeMode(1);
    return {concede:c.concede, weak:c.weak, oppThreat:c.oppThreat, maxOppHu:c.maxOppHu};
  `);
  console.log('## 场景C 弱牌但旁家无威胁');
  testCase('concede=false', r.concede === false, 'maxOppHu=' + r.maxOppHu.toFixed(2));
  testCase('oppThreat=false', r.oppThreat === false, '');
}

// ═══ 场景D：弱牌+威胁大但余牌多 → 不触发 ═══
{
  const r = runCase(`
    _stub.opponentHands[1] = ${WEAK_HAND};  // 自己弱
    ${STRONG_OPP}
    G.deckCount = 80;  // 80/112 ≈ 0.71 → 发展期
    var c = _aiGetConcedeMode(1);
    return {concede:c.concede, weak:c.weak, lateGame:c.lateGame, remainRatio:c.remainRatio};
  `);
  console.log('## 场景D 弱牌+威胁大但余牌多');
  testCase('concede=false', r.concede === false, 'ratio=' + r.remainRatio.toFixed(2));
  testCase('lateGame=false', r.lateGame === false, '');
}

// ═══ 场景E：威胁边界（estPoints 3.5 上下） ═══
{
  const r = runCase(`
    _stub.opponentHands[1] = ${WEAK_HAND};
    // 中等旁家：明牌碰三(1胡) + 手牌单红精 → estPoints 略低于3.5
    _stub.opponentMelds[2] = [{type:'pen', cards:[{ch:'三',v:'skin'},{ch:'三',v:'skin'},{ch:'三',v:'skin'}]}];
    _stub.opponentHands[2] = ['三','化','千','孔','己'];
    _aiHuEstCache = { 1: {sig:'', hu:null}, 2: {sig:'', hu:null} };
    G.deckCount = 30;
    var cLow = _aiGetConcedeMode(1);
    // 强旁家（穿七28胡）→ estPoints 高
    ${STRONG_OPP}
    _aiHuEstCache = { 1: {sig:'', hu:null}, 2: {sig:'', hu:null} };
    var cHigh = _aiGetConcedeMode(1);
    return {low:cLow.maxOppHu, lowThreat:cLow.oppThreat, high:cHigh.maxOppHu, highThreat:cHigh.oppThreat, lowConcede:cLow.concede, highConcede:cHigh.concede};
  `);
  console.log('## 场景E 威胁边界');
  testCase('低威胁(estPoints<3.5) oppThreat=false', r.lowThreat === false, 'maxOppHu=' + r.low.toFixed(2));
  testCase('高威胁(estPoints>=3.5) oppThreat=true', r.highThreat === true, 'maxOppHu=' + r.high.toFixed(2));
  testCase('低威胁不触发concede', r.lowConcede === false, '');
  testCase('高威胁触发concede', r.highConcede === true, '');
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
