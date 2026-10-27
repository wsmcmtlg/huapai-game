// ═══════════════════════════════════════════════════════════════
// measure_winrate.js — 花牌 AI 胡牌率测量工具（主尺）
// 依据：记忆归档/花牌游戏项目分析/08~11 号文档
//   · 双桌口径：校准桌（目标AI+2陪练）/ 体验桌（人类代理+2目标）
//   · 样本纪律：每档 ≥500 局起测、定案 1000 局；±3~4% 为噪声
//   · 决策真身：从 step5-hu.html 自动提取 AI 决策函数（vm 沙箱）
//   · 保险丝：headless Chrome 真身抽检（另行脚本，本工具输出可对比分布）
//
// 用法：
//   node measure_winrate.js --level 3 --games 1000            # 校准桌：3级 vs 2个1级陪练
//   node measure_winrate.js --level 0 --games 500 --seed 42
//   node measure_winrate.js --list                            # 列出可提取函数统计
// 输出：measure_report_L<level>_<games>.json / .md
// ═══════════════════════════════════════════════════════════════
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML_PATH = path.join(__dirname, 'step5-hu.html');
const html = fs.readFileSync(HTML_PATH, 'utf8');

// ── 1. 提取基建（承 test_ai_risk.js 的 extractFunction，扩为括号配平） ──
function extractBalanced(source, startIdx) {
  // 从 startIdx（第一个 { 或 ( 处）配平提取到闭合
  const pairs = { '{': '}', '(': ')', '[': ']' };
  const closers = new Set(['}', ')', ']']);
  let depth = 0, openCh = null, inStr = null;
  for (let i = startIdx; i < source.length; i++) {
    const c = source[i];
    if (inStr) {
      if (c === '\\') { i++; continue; }
      if (c === inStr) inStr = null;
      continue;
    }
    if (c === '"' || c === "'" || c === '`') { inStr = c; continue; }
    // 跳过注释（注释里的括号不参与配平）
    if (c === '/' && source[i + 1] === '/') { while (i < source.length && source[i] !== '\n') i++; continue; }
    if (c === '/' && source[i + 1] === '*') { i += 2; while (i < source.length && !(source[i] === '*' && source[i + 1] === '/')) i++; i++; continue; }
    if (!openCh) {
      if (pairs[c]) { openCh = c; depth = 1; continue; }
      if (c === ';' || c === '\n') return source.slice(startIdx, i); // 无块体的声明，到行尾
      continue;
    }
    if (c === openCh) depth++;
    else if (c === pairs[openCh]) { depth--; if (depth === 0) return source.slice(startIdx, i + 1); }
  }
  return source.slice(startIdx, startIdx + 2000); // 兜底
}
function extractFunction(source, fnAnchor) {
  const start = source.indexOf(fnAnchor);
  if (start < 0) throw new Error('锚点未找到: ' + fnAnchor);
  const brace = source.indexOf('{', start);
  return source.slice(start, brace) + extractBalanced(source, brace); // 保留函数头 + 配平块体
}
// 提取顶层（无缩进）var/let/const NAME = ... 声明，避免误抓函数体内声明行
function extractDecl(source, declAnchor) {
  const re = new RegExp('(?:^|\\n)(?:var|let|const)\\s+' + declAnchor + '\\s*=');
  const m = re.exec(source);
  if (!m) return null;
  const eq = m.index + m[0].length - 1; // m[0] 以 '=' 结尾
  return extractBalanced(source, eq + 1);
}

// ── 2. 预扫描：收集全部函数名与顶层声明名 ──
// 取最长的 <script> 块（主游戏逻辑在 L1936~L9314）
const scriptBodies = [];
{ const re = /<script[^>]*>([\s\S]*?)<\/script>/g; let sm;
  while ((sm = re.exec(html))) scriptBodies.push(sm[1]); }
scriptBodies.sort((a, b) => b.length - a.length);
const scriptBody = scriptBodies[0];
const FN_RE = /function\s+([A-Za-z_$][\w$]*)\s*\(/g;
const allFns = {};   // name -> source
let m;
while ((m = FN_RE.exec(scriptBody))) {
  const name = m[1];
  if (!allFns[name]) {
    try { allFns[name] = extractFunction(scriptBody, 'function ' + name + '('); } catch (e) { /* 多态定义跳过 */ }
  }
}
const KEYWORDS = new Set(['if','for','while','switch','catch','return','function','var','let','const','new','typeof','delete','void','in','of','do','else','break','continue','case','default','throw','try','finally','instanceof','this','arguments','true','false','null','undefined','Math','JSON','Object','Array','String','Number','Boolean','Date','Map','Set','WeakMap','Promise','RegExp','Error','parseInt','parseFloat','isNaN','console','document','window','setTimeout','clearTimeout','setInterval','clearInterval','require','module','exports','Infinity','NaN','Symbol','Reflect','Proxy','alert','confirm','prompt','requestAnimationFrame','performance','localStorage']);
const DECL_RE = /(?:^|\n)(?:var|let|const)\s+([A-Za-z_$][\w$]*)\s*=/g; // 无缩进=顶层声明
const allDecls = {}; // name -> source（或 'STUB'）
while ((m = DECL_RE.exec(scriptBody))) {
  const name = m[1];
  if (allDecls[name] || KEYWORDS.has(name)) continue;
  const src = extractDecl(scriptBody, name);
  if (src == null) continue;
  allDecls[name] = src.includes('document.') || src.includes('window.') ? null : src; // null=DOM stub
}

// ── 3. 依赖自动发现（BFS） ──
const IDENT_RE = /[A-Za-z_$][\w$]*/g;
function discoverDeps(roots) {
  const taken = new Set();
  const queue = [...roots];
  while (queue.length) {
    const name = queue.shift();
    if (taken.has(name)) continue;
    taken.add(name);
    const src = allFns[name] != null ? allFns[name] : (allDecls[name] || '');
    if (!src) continue;
    let im;
    IDENT_RE.lastIndex = 0;
    while ((im = IDENT_RE.exec(src))) {
      const id = im[0];
      if (KEYWORDS.has(id) || taken.has(id)) continue;
      if (allFns[id] !== undefined || allDecls[id] !== undefined) queue.push(id); // DOM 声明值为 null，也收集（装载时换 stub）
    }
  }
  return taken;
}

// ── 4. 沙箱构造 ──
function buildSandbox(seed) {
  const ctx = {
    console: { log(){}, warn(){}, error(){}, info(){} },
    Math: Object.create(Math),
    JSON, Object, Array, String, Number, Boolean, Date, Map, Set, Promise, RegExp, Error,
    parseInt, parseFloat, isNaN, isFinite, Symbol,
    performance: { now: () => Date.now() },
    localStorage: { getItem: () => null, setItem(){}, removeItem(){} },
    // 带种子的 PRNG（可复现对局）
    __seed: seed >>> 0,
  };
  // mulberry32
  ctx.Math.random = function () {
    let t = (ctx.__seed += 0x6D2B79F5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  // 万能 DOM stub：任意属性/方法调用返回自身，赋值静默
  function makeStub() {
    const f = function () { return stub; };
    const stub = new Proxy(f, {
      get: (t, k) => {
        if (k === Symbol.toPrimitive) return () => '';
        if (k === 'length') return 0;
        if (k === 'style' || k === 'dataset' || k === 'classList') return makeStub();
        return stub;
      },
      set: () => true,
      apply: () => stub,
    });
    return stub;
  }
  ctx.document = makeStub();
  ctx.window = ctx;
  ctx.requestAnimationFrame = fn => fn();
  ctx.alert = () => {}; ctx.confirm = () => false; ctx.prompt = () => '';
  // 音效 stub
  ctx.SoundManager = { play(){}, stop(){}, setMuted(){}, init(){} };
  // 同步任务队列替代 setTimeout 链
  const taskQueue = [];
  ctx.__queue = taskQueue;
  ctx.setTimeout = (fn, ms) => { taskQueue.push(fn); return taskQueue.length; };
  ctx.clearTimeout = () => {}; ctx.setInterval = () => 0; ctx.clearInterval = () => {};
  ctx.__makeStub = makeStub; // 供沙箱内 __domStub 使用
  const vmctx = vm.createContext(ctx);
  return { ctx, vmctx, taskQueue };
}

// ── 5. 装载游戏逻辑（函数 + 声明） ──
const ROOT_FNS = [
  'generateDeck', 'aiPickDiscard',
  'checkOpponentHu', 'checkOpponentHuWithCard',
  '_aiDecidePen', '_aiDecideZha', '_aiDecideZhao',
  '_aiCheckOpponentChi', 'calcZhaCount',
  // harness 直接驱动的响应链与庄家流程
  'checkResponseAfterOpponent', 'opponentAutoPlay', 'checkOpponentResponse',
  'dealerZha', 'dealerCheckChuan', 'checkDealerSelfHu', 'checkDealerZhaAndHu',
  'analyzeHand',
];
// 这些声明永远 stub / 特化（不提取真实实现）
const FORCE_STUB = new Set([
  'SoundManager',
  'showSettlePanel',   // 捕获赢家（见注入代码）
  'endGame',           // 捕获荒庄
]);
const INJECT_TAIL = `
;var __winner = null;   // 'win:idx:hu' | 'draw'
function showSettlePanel(winnerIdx, result) { __winner = 'win:' + winnerIdx + ':' + (result && result.totalHu || 0); G.gameOver = true; }
function endGame() { __winner = 'draw'; G.gameOver = true; }
// ── analyzeHand 签名 memo（性能：听牌搜索中同手牌+明牌组合大量重复）──
// ── 分级包装：按 playerIdx 设置该家 aiLevel（否则全局单值，陪练误用目标级大脑）──
var __lvCfg = [3, 1, 1];
var __odp = _aiDecidePen; _aiDecidePen = function(h, ch, pi) { if (__lvCfg[pi] !== undefined) G.aiLevel = __lvCfg[pi]; return __odp(h, ch, pi); };
var __odz = _aiDecideZha; _aiDecideZha = function(h, ch, pi, w) { if (__lvCfg[pi] !== undefined) G.aiLevel = __lvCfg[pi]; return __odz(h, ch, pi, w); };
var __ochi = _aiCheckOpponentChi; _aiCheckOpponentChi = function(pi, ch) { if (__lvCfg[pi] !== undefined) G.aiLevel = __lvCfg[pi]; return __ochi(pi, ch); };
var __opd = aiPickDiscard; aiPickDiscard = function(h, pi) { if (__lvCfg[pi] !== undefined) G.aiLevel = __lvCfg[pi]; return __opd(h, pi); };
var __oap = opponentAutoPlay; opponentAutoPlay = function(pi) { if (__lvCfg[pi] !== undefined) G.aiLevel = __lvCfg[pi]; return __oap(pi); };
var __origAH = analyzeHand; var __ahCache = {};
analyzeHand = function(cards, preMelds) {
  var sig = '';
  for (var i = 0; i < cards.length; i++) { var c = cards[i]; sig += c.ch + (c.isWild ? 'W' : (c.isJin ? (c.v === 'flower' ? 'F' : 'P') : '')); }
  sig += '|';
  if (preMelds) for (var j = 0; j < preMelds.length; j++) sig += preMelds[j].type + ':' + (preMelds[j].chars || []).join('') + ';';
  var hit = __ahCache[sig];
  if (hit !== undefined) return hit;
  var r = __origAH(cards, preMelds);
  __ahCache[sig] = r;
  return r;
};
`;

function loadGameCode() {
  const deps = discoverDeps(ROOT_FNS);
  const chunks = [];
  // 顶层声明（跳过 DOM/特化）
  for (const [name, src] of Object.entries(allDecls)) {
    if (!deps.has(name)) continue;
    if (FORCE_STUB.has(name)) continue;
    if (src == null) { chunks.push('var ' + name + ' = __domStub();'); continue; }
    // DOM 引用的复合声明（如 const handZone = document.getElementById(...)）
    if (src.includes('document.') || src.includes('window.')) { chunks.push('var ' + name + ' = __domStub();'); continue; }
    chunks.push((name === 'G' ? 'var ' : 'var ') + name + ' = ' + src + ';');
  }
  // 函数
  for (const name of deps) {
    if (FORCE_STUB.has(name)) continue;
    const src = allFns[name];
    if (src) chunks.push(src);
  }
  return { chunks: chunks.concat(INJECT_TAIL), deps: [...deps], failures: [] };
}

// ── 6. 单局对局驱动 ──
// 庄家=位0（AI 代理，26张），旁家=位1（下家）、位2（上家）各25张
// 庄家起手扎/碰/招/泛：第一版简化（TODO: 迭代补 dealer 起手流程），仅起手自摸胡检测
function runOneGame(loader, levels, seed) {
  const { ctx, vmctx, taskQueue } = buildSandbox(seed);
  vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
  // 逐条装载，隔离失败项
  for (const chunk of loader.chunks) {
    try { vm.runInContext(chunk, vmctx); }
    catch (e) { loader.failures.push(chunk.slice(0, 60)); }
  }

  ctx.G.gameOver = false;
  ctx.G.aiLevel = levels[0]; // 占位
  // 发牌：庄26/旁25/旁25
  vm.runInContext(`
    G.deck = generateDeck();
    G.deckCount = G.deck.length;
    handCards = []; opponentHands[1] = []; opponentHands[2] = [];
    opponentMelds[1] = []; opponentMelds[2] = [];
    for (let i = 0; i < 26; i++) { var s = G.deck.pop(); handCards.push(s.indexOf(':')>=0 ? s.substring(0,s.indexOf(':')) : s); }
    for (let p = 1; p <= 2; p++) for (let i = 0; i < 25; i++) { var s2 = G.deck.pop(); opponentHands[p].push(s2.indexOf(':')>=0 ? s2.substring(0,s2.indexOf(':')) : s2); }
    G.deckCount = G.deck.length;
    G._passRecord = {}; G._skippedOps = {};
    G.dealerMelds = G.dealerMelds || [];   // 页面靠延迟初始化，测量环境需显式补齐
    __lvCfg[0] = " + levels[0] + "; __lvCfg[1] = " + levels[1] + "; __lvCfg[2] = " + levels[2] + ";
  `, vmctx);

  // 统计循环：驱动任务队列 + 庄家回合接管
  // 庄家流程：摸牌→扎检测→自摸胡→出牌→checkResponseAfterOpponent(0)
  let guard = 0;
  const MAX_STEPS = 20000;
  const runDealerTurn = (first) => {
    // 庄家摸牌（首回合起手 26 张不摸）
    if (!first) {
      if (ctx.G.deckCount > 0) {
        const s = ctx.G.deck.pop(); ctx.handCards.push(s.indexOf(':') >= 0 ? s.substring(0, s.indexOf(':')) : s);
        ctx.G.deckCount--;
      } else { ctx.__winner = 'draw'; ctx.G.gameOver = true; return; }
    }
    ctx.G.aiLevel = levels[0];
    // 摸后自摸胡检测（庄家手牌在 handCards，不在 opponentHands，直接用 analyzeHand）
    const hu = vm.runInContext('analyzeHand(handCards.map(c => makeCardData(c)))', vmctx);
    if (hu && hu.isWin) { ctx.__winner = 'win:0:' + (hu.totalHu || 0); ctx.G.gameOver = true; return; }
    // 出牌（TODO 迭代：庄家扎检测/穿/泛、忍扎决策）
    const idx = vm.runInContext('aiPickDiscard(handCards, 0)', vmctx);
    if (typeof idx !== 'number' || idx < 0 || idx >= ctx.handCards.length) { ctx.__winner = 'draw'; ctx.G.gameOver = true; return; }
    const played = ctx.handCards.splice(idx, 1)[0];
    ctx.G.lastPlayedChar = played;
    ctx.G.lastPlayedFrom = 0;
    taskQueue.push(() => { try { vm.runInContext('checkResponseAfterOpponent(0)', vmctx); } catch (e) { ctx.__winner = 'draw'; ctx.G.gameOver = true; } });
  };
  // 首回合入队
  taskQueue.push(() => runDealerTurn(true));
  // 主循环：队列驱动（页面 setTimeout 链）+ 空队列时庄家接管
  while (!ctx.G.gameOver && guard++ < MAX_STEPS) {
    if (taskQueue.length) {
      const fn = taskQueue.shift();
      try { fn(); }
      catch (e) {
        // 异常分类：querySelector/innerHTML 等 DOM 类吞掉；其它（流程类）上报终止本局
        const msg = e && e.message || '';
        if (/querySelector|innerHTML|classList|style|appendChild|textContent/.test(msg)) continue;
        ctx.__err = msg; ctx.G.gameOver = true;
      }
    }
    else { runDealerTurn(); }
    // G.gameOver 由 showSettlePanel/endGame stub 设置
  }
  if (guard >= MAX_STEPS) return { winner: 'stuck', hu: 0 };
  const w = ctx.__winner || 'draw';
  if (w.startsWith('win:')) { const [, pi, hu] = w.split(':'); return { winner: +pi, hu: +hu }; }
  return { winner: -1, hu: 0 }; // 荒庄
}

// ── 7. 统计与报告 ──
function wilsonCI(p, n, z = 1.96) {
  if (n === 0) return [0, 0];
  const d = 1 + z * z / n;
  const c = p + z * z / (2 * n);
  const r = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n));
  return [(c - r) / d, (c + r) / d];
}
function main() {
  const args = process.argv.slice(2);
  if (args.includes('--list')) {
    const { deps } = loadGameCode();
    console.log('提取函数/声明数:', deps.length); console.log(deps.sort().join(', ')); return;
  }
  const getArg = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
  const level = +getArg('--level', 3);
  const games = +getArg('--games', 500);
  const seed = +getArg('--seed', 20261027);
  const levelNames = ['菜鸟', '高手', '大师', '老千'];
  // 校准桌：目标级(位0庄) + 2 个高手陪练
  const levels = [level, 1, 1];
  console.log(`校准桌：位0=${levelNames[level]}(庄) vs 位1/位2=高手陪练 × ${games} 局`);
  const loader = loadGameCode();
  console.log('已提取依赖函数/声明:', loader.deps.length, '个');
  const wins = [0, 0, 0]; let draws = 0, stuck = 0; const huList = [];
  for (let g = 0; g < games; g++) {
    process.stdout.write(`\r局 ${g + 1}/${games}`);
    let r;
    try { r = runOneGame(loader, levels, seed + g * 7919); }
    catch (e) { r = { winner: 'error', hu: 0, msg: e.message + ' @ ' + (e.stack || '').split('\n')[1] } }
    if (r.winner === -1 || r.winner === 'draw') draws++;
    else if (r.winner === 'stuck' || r.winner === 'error') { stuck++; if (stuck <= 5) console.log('\n异常:', (r.msg || r.winner).slice(0, 160)); fs.appendFileSync(path.join(__dirname, 'measure_errors.log'), JSON.stringify({ g, r: r.winner, msg: r.msg }) + '\n'); }
    else { wins[r.winner]++; huList.push(r.hu); }
  }
  console.log('');
  const decided = games - draws - stuck;
  const lines = [`# 测量报告：${levelNames[level]}（位0庄） vs 2×高手陪练`, '',
    `- 对局数：${games}（胡牌终局 ${decided}，荒庄 ${draws}，异常 ${stuck}）`];
  for (let pi = 0; pi < 3; pi++) {
    const p = wins[pi] / games;
    const [lo, hi] = wilsonCI(p, games);
    lines.push(`- 位${pi}（${pi === 0 ? levelNames[level] : '高手陪练'}）：胡牌率 ${(p * 100).toFixed(1)}%  [95%CI ${(lo * 100).toFixed(1)}~${(hi * 100).toFixed(1)}]  （${wins[pi]} 胜）`);
  }
  if (huList.length) {
    const avg = huList.reduce((a, b) => a + b, 0) / huList.length;
    lines.push(`- 平均胡数（赢家）：${avg.toFixed(1)}`);
  }
  const report = lines.join('\n');
  console.log('\n' + report);
  const base = `measure_report_L${level}_${games}`;
  fs.writeFileSync(path.join(__dirname, base + '.md'), report);
  fs.writeFileSync(path.join(__dirname, base + '.json'), JSON.stringify({ level, games, seed, wins, draws, stuck }, null, 2));
  console.log('已写入', base + '.md /', base + '.json');
}
main();
