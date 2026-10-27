// _d38.js — 庄家捉铳/自摸成交诊断（含 drawnCard 修复版 harness）
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

const GAMES = 10;
let tot = { pw: 0, selfWin: 0, looseWinAtDraw: 0, looseNon: 0, looseCalls: 0, oppWin: 0 };

for (let g = 0; g < GAMES; g++) {
  const seed = 20261027 + g * 7919;
  const { ctx, vmctx, taskQueue } = buildSandbox(seed);
  vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
  const probe = `
    ;var __cnt = { pw: 0, looseWin: 0, looseNon: 0, looseCalls: 0 };
    var __ol = analyzeHandLoose;
    analyzeHandLoose = function(cards, preMelds) {
      __cnt.looseCalls++;
      var r = __ol(cards, preMelds);
      if (r && r.isWin) {
        var sig1 = '', sig2 = '';
        for (var qi = 0; qi < cards.length; qi++) sig1 += cards[qi].ch + ',';
        for (var qj = 0; qj < handCards.length; qj++) sig2 += handCards[qj] + ',';
        if (sig1 === sig2 && (!preMelds || preMelds.length === 0)) __cnt.looseWin++;   // 精确匹配庄家手牌且无明牌
      }
      if (r) __cnt.looseNon++; else __cnt.looseCallsNull = (__cnt.looseCallsNull||0)+1;
      return r;
    };
  `;
  for (const chunk of loadGameCode().chunks.concat([probe])) {
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

  let dealerTurns = 0;
  const runDealerTurn = (first) => {
    dealerTurns++;
    if (!first) {
      if (ctx.G.deckCount > 0) {
        const s = ctx.G.deck.pop(); const sc = s.indexOf(':') >= 0 ? s.substring(0, s.indexOf(':')) : s;
        ctx.handCards.push(sc); ctx.G.deckCount--;
        ctx.G.drawnCard = vm.runInContext('makeCardData(' + JSON.stringify(sc) + ')', vmctx);
      } else { ctx.__winner = 'draw'; ctx.G.gameOver = true; return; }
    }
    ctx.G.aiLevel = 3;
    const hu = vm.runInContext('analyzeHand(handCards.map(c => makeCardData(c)))', vmctx);
    if (hu && hu.isWin) { tot.selfWin++; ctx.__winner = 'win:0:' + hu.totalHu; ctx.G.gameOver = true; return; }
    const idx = vm.runInContext('aiPickDiscard(handCards, 0)', vmctx);
    if (typeof idx !== 'number' || idx < 0 || idx >= ctx.handCards.length) { ctx.__winner = 'draw'; ctx.G.gameOver = true; return; }
    const played = ctx.handCards.splice(idx, 1)[0];
    ctx.G.lastPlayedChar = played; ctx.G.lastPlayedFrom = 0; ctx.G.drawnCard = null;
    taskQueue.push(() => { try { vm.runInContext('checkResponseAfterOpponent(0)', vmctx); } catch (e) { const m=e.message||''; if (!/querySelector|innerHTML|classList|style|appendChild|textContent|addEventListener/.test(m)) { ctx.__err = m; ctx.G.gameOver = true; } } });
  };
  taskQueue.push(() => runDealerTurn(true));
  let guard = 0;
  while (!ctx.G.gameOver && guard++ < 20000) {
    if (taskQueue.length) {
      const fn = taskQueue.shift();
      try { fn(); }
      catch (e) { const m = e && e.message || ''; if (!/querySelector|innerHTML|classList|style|appendChild|textContent|addEventListener/.test(m)) { ctx.__err = m; ctx.G.gameOver = true; } }
      if (ctx.G._pendingWin) { tot.pw++; ctx.__winner = 'win:0:' + (ctx.G._pendingWin.totalHu || 0); ctx.G.gameOver = true; ctx.G._pendingWin = null; }
    } else runDealerTurn();
  }
  const c = ctx.__cnt;
  tot.looseWinAtDraw += c.looseWin; tot.looseCalls += c.looseCalls; tot.looseNon += c.looseNon;
  log(`局${g}: ${ctx.__winner || '?'} err=${ctx.__err || '-'} 庄回合=${dealerTurns} pw=${c.pw} 真实手牌loose胡=${c.looseWin} loose非null=${c.looseNon}/${c.looseCalls}`);
}
log(`\n汇总: 庄家捉铳=${tot.pw} 庄自摸=${tot.selfWin} 真实手牌达胡(loose)=${tot.looseWinAtDraw} loose调用=${tot.looseCalls}`);
fs.writeFileSync('_d38_out.txt', OUT.join('\n'), 'utf8');
console.log(OUT.join('\n'));
