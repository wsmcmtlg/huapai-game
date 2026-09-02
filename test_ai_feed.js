// ═══════════════════════════════════════════════════════
// Phase 7.6 单测：主动喂牌（止损模式下引导便宜玩家胡牌）
// 覆盖：
//   场景A: 两家胡数差距明显 → 识别便宜家为喂牌目标
//   场景B: 两家胡数相近 → 不喂（差距<1）
//   场景C: 便宜家无胡牌潜力 → 不喂
//   场景D: feedScore 分家评分（便宜家需要→正、危险家需要→负）
//   场景E: 过牌记录降权（便宜家过过的牌）
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
funcs.push(extractFunction(html, 'function _aiGetFeedTarget(playerIdx) {')); // 喂牌目标
funcs.push(extractFunction(html, 'function _aiFeedScore(ch, feedTarget) {')); // 喂牌评分

// ── 环境桩 ──
const stubCode = `
var _stub = {
  opponentHands: { 1: [], 2: [] },
  opponentMelds: { 1: [], 2: [] },
  G: { _passRecord: {}, mainJin: '三', deckCount: 30 },
  remainMap: {},
  tingGuess: { 1: [], 2: [] },
  behaviorGuess: { 1: [], 2: [] }
};
var opponentHands = _stub.opponentHands;
var opponentMelds = _stub.opponentMelds;
var G = _stub.G;
// G_CARD_TOTALS 简化版：22字面×5 + 赖2 = 112
var G_CARD_TOTALS = {};
(function(){ var allC = '上大人可知礼化三千孔乙己七十土八九子二四五六七八九十赖'; for (var i=0;i<allC.length;i++) G_CARD_TOTALS[allC[i]] = 5; G_CARD_TOTALS['赖'] = 2; })();
function getRemainingCount(ch) { return 3; }
// 生成完整卡片对象（与 makeCardData 字段一致：isJin/isWild/c/v）
function mkCard(ch, v) {
  var isJin = '三五七乙九'.indexOf(ch) >= 0;
  var isWild = ch === '赖';
  return { ch: ch, c: isJin ? 1 : 0, v: v || (isJin ? 'flower' : 'skin'), isJin: isJin, isWild: isWild };
}
function guessOpponentTing(pi) { return _stub.tingGuess[pi] || []; }
function _aiBehaviorBasedTingGuess(pi) { return _stub.behaviorGuess[pi] || []; }
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

// 强旁家(pi=2)：穿七2花3皮 → meldHu=28 查表精确 + 三三三赖赖 → estPoints 高（8分）
const STRONG_OPP2 = `
  _stub.opponentMelds[2] = [
    {type:'chuan', cards:[mkCard('七','flower'),mkCard('七','flower'),mkCard('七','skin'),mkCard('七','skin'),mkCard('七','skin')]}
  ];
  _stub.opponentHands[2] = ['三','三','三','赖','赖'];
`;
// 弱旁家(pi=1)：无明牌，手牌含1赖子 → estPoints≈0.53（有潜力但远低于危险家）
const WEAK_OPP1 = `
  _stub.opponentMelds[1] = [];
  _stub.opponentHands[1] = ['赖','化','千','孔','己','子','八','九','十','二'];
`;

// ═══ 场景A：两家差距明显 → 识别便宜家 ═══
{
  const r = runCase(`
    ${STRONG_OPP2}
    ${WEAK_OPP1}
    _aiHuEstCache = { 1: {sig:'', hu:null}, 2: {sig:'', hu:null} };
    var t = _aiGetFeedTarget(0);  // 出牌者是庄家视角，两家旁家都是对手
    return {target:t ? t.targetPi : null, danger:t ? t.dangerPi : null,
            targetP:t ? t.targetPoints : 0, dangerP:t ? t.dangerPoints : 0, diff:t ? t.diff : 0};
  `);
  console.log('## 场景A 差距明显 → 识别便宜家');
  testCase('识别便宜家(pi=1)为喂牌目标', r.target === 1, 'target=' + r.target + ' danger=' + r.danger);
  testCase('危险家为pi=2', r.danger === 2, '');
  testCase('便宜家胡数 < 危险家胡数', r.targetP < r.dangerP, 'targetP=' + r.targetP.toFixed(2) + ' dangerP=' + r.dangerP.toFixed(2));
  testCase('差距>=1', r.diff >= 1.0, 'diff=' + r.diff.toFixed(2));
}

// ═══ 场景B：两家胡数相近 → 不喂 ═══
{
  const r = runCase(`
    // 两家都较弱但胡数接近（五碰 vs 七碰，均非主精'三'）
    _stub.opponentMelds[1] = [{type:'pen', cards:[mkCard('五','skin'),mkCard('五','skin'),mkCard('五','skin')]}];
    _stub.opponentMelds[2] = [{type:'pen', cards:[mkCard('七','skin'),mkCard('七','skin'),mkCard('七','skin')]}];
    _stub.opponentHands[1] = ['化','千','孔','己','子'];
    _stub.opponentHands[2] = ['上','大','人','可','知'];
    _aiHuEstCache = { 1: {sig:'', hu:null}, 2: {sig:'', hu:null} };
    var t = _aiGetFeedTarget(0);
    return {target:t ? t.targetPi : null, diff:t ? t.diff : 0};
  `);
  console.log('## 场景B 两家相近');
  testCase('不识别喂牌目标(null)', r.target === null, 'diff=' + (r.diff||0).toFixed(2));
}

// ═══ 场景C：便宜家无胡牌潜力 → 不喂 ═══
{
  const r = runCase(`
    // 危险家强，但便宜家完全无牌力（estPoints≈0）
    ${STRONG_OPP2}
    _stub.opponentMelds[1] = [];
    _stub.opponentHands[1] = ['化','千','孔','己','子'];
    _aiHuEstCache = { 1: {sig:'', hu:null}, 2: {sig:'', hu:null} };
    var t = _aiGetFeedTarget(0);
    return {target:t ? t.targetPi : null, cheapP: t ? t.targetPoints : 0};
  `);
  console.log('## 场景C 便宜家无潜力');
  testCase('不识别喂牌目标(null)', r.target === null, 'cheapP=' + r.cheapP.toFixed(2));
}

// ═══ 场景D：feedScore 分家评分 ═══
{
  const r = runCase(`
    ${STRONG_OPP2}
    ${WEAK_OPP1}
    _aiHuEstCache = { 1: {sig:'', hu:null}, 2: {sig:'', hu:null} };
    var t = _aiGetFeedTarget(0);
    // 便宜家(1)需要'上'，危险家(2)需要'化'
    _stub.tingGuess[1] = [{ch:'上', c:0.8}];
    _stub.tingGuess[2] = [{ch:'化', c:0.8}];
    var feedShang = _aiFeedScore('上', t);  // 便宜家需要 → 正
    var feedHua = _aiFeedScore('化', t);    // 危险家需要 → 负
    var feedNeutral = _aiFeedScore('大', t); // 两家都不需要 → 0
    return {feedShang:feedShang, feedHua:feedHua, feedNeutral:feedNeutral};
  `);
  console.log('## 场景D feedScore 分家评分');
  testCase('便宜家需要的牌 feedScore>0', r.feedShang > 0, '上=' + r.feedShang.toFixed(2));
  testCase('危险家需要的牌 feedScore<0', r.feedHua < 0, '化=' + r.feedHua.toFixed(2));
  testCase('两家都不需要的牌 feedScore≈0', Math.abs(r.feedNeutral) < 0.01, '大=' + r.feedNeutral);
}

// ═══ 场景E：过牌记录降权 ═══
{
  const r = runCase(`
    ${STRONG_OPP2}
    ${WEAK_OPP1}
    _aiHuEstCache = { 1: {sig:'', hu:null}, 2: {sig:'', hu:null} };
    var t = _aiGetFeedTarget(0);
    _stub.tingGuess[1] = [{ch:'上', c:0.8}];
    var before = _aiFeedScore('上', t);
    _stub.G._passRecord[1] = { '上': true };  // 便宜家过过'上'
    var after = _aiFeedScore('上', t);
    return {before:before, after:after};
  `);
  console.log('## 场景E 过牌降权');
  testCase('过过的牌分数降低', r.after < r.before, 'before=' + r.before.toFixed(2) + ' after=' + r.after.toFixed(2));
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
