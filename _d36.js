// _d36.js — 捉铳/听牌成交诊断
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const mwSrc = fs.readFileSync(path.join(__dirname, 'measure_winrate.js'), 'utf8')
  .replace(/\nmain\(\);\s*$/, '\n')
  .replace("'use strict';", '')
  .replace(/\bconst /g, 'var ');
globalThis.require = require; globalThis.__dirname = __dirname;
globalThis.module = { exports: {} }; globalThis.process = process;
(0, eval)(mwSrc);

const OUT = [];
const log = s => OUT.push(String(s));

const probe = `
;var __cnt = { pendingWin: 0, oppHuCheck: 0, oppHuReady: 0, oppHuWin: 0, dealerSelfHuChk: 0, dealerSelfHuWin: 0 };
var __ohu = checkOpponentHu;
checkOpponentHu = function(pi) { __cnt.oppHuCheck++; var r = __ohu(pi); if (r) { __cnt.oppHuReady++; if (r.isWin) __cnt.oppHuWin++; } return r; };
`;
// 庄家自摸检测（harness 内 analyzeHand）单独计

const GAMES = 20;
let totals = { pendingWin: 0, oppHuCheck: 0, oppHuReady: 0, oppHuWin: 0 };
const dealerHuNear = [];

for (let g = 0; g < GAMES; g++) {
  const seed = 20261027 + g * 7919;
  const { ctx, vmctx, taskQueue } = buildSandbox(seed);
  vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
  const loader = loadGameCode();
  for (const chunk of loader.chunks.concat([probe])) {
    try { vm.runInContext(chunk, vmctx); } catch (e) { log('装载失败:' + chunk.slice(0, 50) + '::' + e.message); }
  }

  ctx.G.gameOver = false; ctx.G.aiLevel = 3;
  vm.runInContext(`
    G.deck = generateDeck(); G.deckCount = G.deck.length;
    handCards = []; opponentHands[1] = []; opponentHands[2] = [];
    opponentMelds[1] = []; opponentMelds[2] = [];
    for (let i = 0; i < 26; i++) { var s = G.deck.pop(); handCards.push(s.indexOf(':')>=0 ? s.substring(0,s.indexOf(':')) : s); }
    for (let p = 1; p <= 2; p++) for (let i = 0; i < 25; i++) { var s2 = G.deck.pop(); opponentHands[p].push(s2.indexOf(':')>=0 ? s2.substring(0,s2.indexOf(':')) : s2); }
    G.deckCount = G.deck.length;
    G._passRecord = {}; G._skippedOps = {}; G.dealerMelds = G.dealerMelds || [];
    __lvCfg[0] = 3; __lvCfg[1] = 1; __lvCfg[2] = 1;
  `, vmctx);

  let dealerTurns = 0, dealerHuChk = 0, dealerHuWin = 0;
  const runDealerTurn = (first) => {
    dealerTurns++;
    if (!first) {
      if (ctx.G.deckCount > 0) { const s = ctx.G.deck.pop(); ctx.handCards.push(s.indexOf(':')>=0?s.substring(0,s.indexOf(':')):s); ctx.G.deckCount--; }
      else { ctx.__winner = 'draw'; ctx.G.gameOver = true; return; }
    }
    ctx.G.aiLevel = 3;
    dealerHuChk++;
    const hu = vm.runInContext('analyzeHand(handCards.map(c => makeCardData(c)))', vmctx);
    if (hu && hu.isWin) { dealerHuWin++; ctx.__winner = 'win:0:' + hu.totalHu; ctx.G.gameOver = true; return; }
    const idx = vm.runInContext('aiPickDiscard(handCards, 0)', vmctx);
    if (typeof idx !== 'number' || idx < 0 || idx >= ctx.handCards.length) { ctx.__winner = 'draw'; ctx.G.gameOver = true; return; }
    const played = ctx.handCards.splice(idx, 1)[0];
    ctx.G.lastPlayedChar = played; ctx.G.lastPlayedFrom = 0;
    taskQueue.push(() => { try { vm.runInContext('checkResponseAfterOpponent(0)', vmctx); } catch (e) { ctx.__winner = 'draw'; ctx.G.gameOver = true; } });
    // 捉铳轮询点：任务队列跑完后检查
    taskQueue.push(() => {
      if (ctx.G._pendingWin) { ctx.__cnt.pendingWin++; ctx.__winner = 'win:0:' + (ctx.G._pendingWin.totalHu || 0); ctx.G.gameOver = true; ctx.G._pendingWin = null; }
    });
  };
  taskQueue.push(() => runDealerTurn(true));

  let guard = 0;
  while (!ctx.G.gameOver && guard++ < 20000) {
    if (taskQueue.length) {
      const fn = taskQueue.shift();
      try { fn(); }
      catch (e) { const msg = e && e.message || ''; if (/querySelector|innerHTML|classList|style|appendChild|textContent/.test(msg)) continue; ctx.__winner = 'draw'; ctx.G.gameOver = true; }
    } else runDealerTurn();
  }
  const c = ctx.__cnt;
  totals.pendingWin += c.pendingWin; totals.oppHuCheck += c.oppHuCheck;
  totals.oppHuReady += c.oppHuReady; totals.oppHuWin += c.oppHuWin;
  log(`局${g}: ${ctx.__winner} 庄回合=${dealerTurns} 庄自摸chk=${dealerHuChk}/win=${dealerHuWin} pendingWin=${c.pendingWin} 旁家hu检测=${c.oppHuCheck}/ready=${c.oppHuReady}/win=${c.oppHuWin}`);
}
log(`\n汇总: 庄家捉铳=${totals.pendingWin} 旁家捉铳win=${totals.oppHuWin}/${totals.oppHuReady}/${totals.oppHuCheck}`);
fs.writeFileSync('_d36_out.txt', OUT.join('\n'), 'utf8');
console.log(OUT.join('\n'));
