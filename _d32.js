// _d32.js — 诊断：AI 为何从不胡牌（全荒庄）
// 统计：analyzeHandLoose 调用/结构全拆(structOK)/胡数达标(win17)/最大胡数分布
//      + 终局三家牌力：analyzeHand totalHu、明牌组数、手牌张数
// 复用 measure_winrate.js 基建（去掉 main() 调用后 eval）
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

// 去掉 strict 与 main()，const→var 后在本进程作用域 eval，函数直接可用
const mwSrc = fs.readFileSync(path.join(__dirname, 'measure_winrate.js'), 'utf8')
  .replace(/\nmain\(\);\s*$/, '\n')
  .replace("'use strict';", '')
  .replace(/\bconst /g, 'var ');
globalThis.require = require; globalThis.__dirname = __dirname; globalThis.module = { exports: {} }; globalThis.process = process;
(0, eval)(mwSrc); // 间接 eval：var/function 声明挂到 globalThis

const OUT = [];
const log = s => OUT.push(String(s));

const loader = loadGameCode();
log('依赖数: ' + loader.deps.length);
if (loader.failures.length) log('failures: ' + JSON.stringify(loader.failures.slice(0, 10)));

const GAMES = 20;
const stats = { looseCalls: 0, structOK: 0, win17: 0, maxHuSum: 0, maxHuMax: 0, ahCalls: 0, ahWin: 0, ahHuSum: 0, ahHuMax: 0 };
const endGames = [];

for (let g = 0; g < GAMES; g++) {
  const levels = [3, 1, 1];
  const seed = 20261027 + g * 7919;
  const { ctx, vmctx, taskQueue } = buildSandbox(seed);
  vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
  // 装载 + 计数探针
  const probe = `
    ;var __probe = { looseCalls: 0, structOK: 0, win17: 0, maxHuSum: 0, maxHuMax: 0 };
    var __ol = analyzeHandLoose;
    analyzeHandLoose = function(cards, preMelds) {
      __probe.looseCalls++;
      var r = __ol(cards, preMelds);
      if (r) {
        if (r.melds && r.melds.length > 0) __probe.structOK++;
        __probe.maxHuSum += (r.totalHu || 0);
        if ((r.totalHu || 0) > __probe.maxHuMax) __probe.maxHuMax = r.totalHu || 0;
        if ((r.totalHu || 0) >= 17) __probe.win17++;
      }
      return r;
    };
  `;
  for (const chunk of loader.chunks.concat(probe)) {
    try { vm.runInContext(chunk, vmctx); }
    catch (e) { log('装载失败: ' + chunk.slice(0, 60) + ' :: ' + e.message); }
  }

  ctx.G.gameOver = false; ctx.G.aiLevel = levels[0];
  vm.runInContext(`
    G.deck = generateDeck();
    G.deckCount = G.deck.length;
    handCards = []; opponentHands[1] = []; opponentHands[2] = [];
    opponentMelds[1] = []; opponentMelds[2] = [];
    for (let i = 0; i < 26; i++) { var s = G.deck.pop(); handCards.push(s.indexOf(':')>=0 ? s.substring(0,s.indexOf(':')) : s); }
    for (let p = 1; p <= 2; p++) for (let i = 0; i < 25; i++) { var s2 = G.deck.pop(); opponentHands[p].push(s2.indexOf(':')>=0 ? s2.substring(0,s2.indexOf(':')) : s2); }
    G.deckCount = G.deck.length;
    G._passRecord = {}; G._skippedOps = {};
    G.dealerMelds = G.dealerMelds || [];
    __lvCfg[0] = 3; __lvCfg[1] = 1; __lvCfg[2] = 1;
  `, vmctx);

  let guard = 0;
  const MAX_STEPS = 20000;
  const runDealerTurn = (first) => {
    if (!first) {
      if (ctx.G.deckCount > 0) {
        const s = ctx.G.deck.pop(); ctx.handCards.push(s.indexOf(':') >= 0 ? s.substring(0, s.indexOf(':')) : s);
        ctx.G.deckCount--;
      } else { ctx.__winner = 'draw'; ctx.G.gameOver = true; return; }
    }
    ctx.G.aiLevel = 3;
    const hu = vm.runInContext('analyzeHand(handCards.map(c => makeCardData(c)))', vmctx);
    if (hu && hu.isWin) { ctx.__winner = 'win:0:' + (hu.totalHu || 0); ctx.G.gameOver = true; return; }
    const idx = vm.runInContext('aiPickDiscard(handCards, 0)', vmctx);
    if (typeof idx !== 'number' || idx < 0 || idx >= ctx.handCards.length) { ctx.__winner = 'draw'; ctx.G.gameOver = true; return; }
    const played = ctx.handCards.splice(idx, 1)[0];
    ctx.G.lastPlayedChar = played; ctx.G.lastPlayedFrom = 0;
    taskQueue.push(() => { try { vm.runInContext('checkResponseAfterOpponent(0)', vmctx); } catch (e) { ctx.__winner = 'draw'; ctx.G.gameOver = true; } });
  };
  taskQueue.push(() => runDealerTurn(true));
  while (!ctx.G.gameOver && guard++ < MAX_STEPS) {
    if (taskQueue.length) {
      const fn = taskQueue.shift();
      try { fn(); }
      catch (e) {
        const msg = e && e.message || '';
        if (/querySelector|innerHTML|classList|style|appendChild|textContent/.test(msg)) continue;
        ctx.__err = msg; ctx.G.gameOver = true;
      }
    } else { runDealerTurn(); }
  }

  // 汇总本局
  const p = ctx.__probe || {};
  const w = ctx.__winner || 'draw';
  stats.looseCalls += p.looseCalls || 0; stats.structOK += p.structOK || 0;
  stats.win17 += p.win17 || 0; stats.maxHuSum += p.maxHuSum || 0;
  if ((p.maxHuMax || 0) > stats.maxHuMax) stats.maxHuMax = p.maxHuMax;
  log(`局${g}: result=${w} err=${ctx.__err || '-'} looseCalls=${p.looseCalls || 0} structOK=${p.structOK || 0} win17=${p.win17 || 0} maxHu=${p.maxHuMax || 0} avgHu=${p.looseCalls ? ((p.maxHuSum / p.looseCalls)).toFixed(1) : '-'}`);

  // 终局牌力快照
  const snap = vm.runInContext(`
    (function(){
      function one(cards, melds) {
        var md = cards.map(function(c){ return makeCardData(c); });
        var a = analyzeHand(md);
        var l = analyzeHandLoose(md, melds || []);
        return { n: cards.length, melds: (melds||[]).length, hu: a ? (a.totalHu||0) : -1, isWin: !!(a && a.isWin), looseHu: l ? (l.totalHu||0) : -1, looseStruct: l ? (l.structCount||0) : -1 };
      }
      return '庄:' + JSON.stringify(one(handCards, G.dealerMelds)) +
             ' 下:' + JSON.stringify(one(opponentHands[1], opponentMelds[1])) +
             ' 上:' + JSON.stringify(one(opponentHands[2], opponentMelds[2]));
    })()
  `, vmctx);
  log('   ' + snap);
  endGames.push(snap);
}

log('\n═══ 汇总（' + GAMES + ' 局）═══');
log(`looseCalls=${stats.looseCalls}  structOK=${stats.structOK}  win17=${stats.win17}  maxHuMax=${stats.maxHuMax}  avgMaxHu=${(stats.maxHuSum / Math.max(1, stats.looseCalls)).toFixed(2)}`);

fs.writeFileSync(path.join(__dirname, '_diag_out.txt'), OUT.join('\n'), 'utf8');
console.log(OUT.join('\n'));
