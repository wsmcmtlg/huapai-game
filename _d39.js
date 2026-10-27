// _d39.js — 庄家 26 张 analyzeHand 调用分布 + 听牌率
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
let tot = { ah26: 0, ah26win: 0, ah26huSum: 0, ah26huMax: 0, selfChk: 0, selfWin: 0, ting: 0, turns: 0, pw: 0 };

for (let g = 0; g < GAMES; g++) {
  const seed = 20261027 + g * 7919;
  const { ctx, vmctx, taskQueue } = buildSandbox(seed);
  vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
  const probe = `
    ;var __cnt = { ah26: 0, ah26win: 0, ah26huSum: 0, ah26huMax: 0 };
    var __oah = analyzeHand;
    analyzeHand = function(cards, preMelds) {
      var r = __oah(cards, preMelds);
      if (cards && cards.length === 26 && !G.gameOver) {
        __cnt.ah26++;
        if (r) { __cnt.ah26huSum += (r.totalHu||0); if ((r.totalHu||0) > __cnt.ah26huMax) __cnt.ah26huMax = r.totalHu||0; if (r.isWin) __cnt.ah26win++; }
      }
      return r;
    };
    var __ol = analyzeHandLoose;
    analyzeHandLoose = function(cards, preMelds) {
      var r = __ol(cards, preMelds);
      if (cards && cards.length === handCards.length && cards[0] === handCards[0] && r) __cnt.realLoose = (__cnt.realLoose||0)+1;
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
    for (let i = 0; i < 26; i++) handCards.push(parseDeckCard(G.deck.pop()));
    for (let p = 1; p <= 2; p++) for (let i = 0; i < 25; i++) { var s2 = G.deck.pop(); opponentHands[p].push(s2.indexOf(':')>=0 ? s2.substring(0,s2.indexOf(':')) : s2); }
    G.deckCount = G.deck.length;
    G._passRecord = {}; G._skippedOps = {}; G.dealerMelds = G.dealerMelds || [];
    __lvCfg[0] = 3; __lvCfg[1] = 1; __lvCfg[2] = 1;
  `, vmctx);

  const runDealerTurn = (first) => {
    tot.turns++;
    if (!first) {
      if (ctx.G.deckCount > 0) {
        const cd = vm.runInContext('parseDeckCard(G.deck.pop())', vmctx);
        ctx.handCards.push(cd); ctx.G.deckCount--; ctx.G.drawnCard = cd;
      } else { ctx.__winner = 'draw'; ctx.G.gameOver = true; return; }
    }
    ctx.G.aiLevel = 3;
    tot.selfChk++;
    const hu = vm.runInContext('analyzeHand(handCards.slice())', vmctx);
    if (hu && hu.isWin) { tot.selfWin++; ctx.__winner = 'win:0:' + hu.totalHu; ctx.G.gameOver = true; return; }
    // 听牌统计：弃任一张后能否全拆+17胡
    const ting = vm.runInContext(`
      (function(){
        for (var i = 0; i < handCards.length; i++) {
          var test = handCards.slice(); test.splice(i,1);
          var r = analyzeHandLoose(test);
          if (r && r.isWin) return 1;
        }
        return 0;
      })()
    `, vmctx);
    tot.ting += ting;
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
      try { fn(); } catch (e) { const m = e && e.message || ''; if (!/querySelector|innerHTML|classList|style|appendChild|textContent|addEventListener/.test(m)) { ctx.__err = m; ctx.G.gameOver = true; } }
      if (ctx.G._pendingWin) { tot.pw++; ctx.__winner = 'win:0:' + (ctx.G._pendingWin.totalHu || 0); ctx.G.gameOver = true; ctx.G._pendingWin = null; }
    } else runDealerTurn();
  }
  const c = ctx.__cnt;
  tot.ah26 += c.ah26; tot.ah26win += c.ah26win; tot.ah26huSum += c.ah26huSum;
  if (c.ah26huMax > tot.ah26huMax) tot.ah26huMax = c.ah26huMax;
  log(`局${g}: ${ctx.__winner || '?'} err=${ctx.__err||'-'} 26张分析=${c.ah26} 其中胡=${c.ah26win} avgHu=${c.ah26? (c.ah26huSum/c.ah26).toFixed(1):'-'} maxHu=${c.ah26huMax} 真实loose调用=${c.realLoose||0}`);
}
log(`\n汇总: 庄回合=${tot.turns} 自摸chk=${tot.selfChk} 自摸win=${tot.selfWin} 听牌回合数=${tot.ting} 捉铳26张分析=${tot.ah26} 达胡=${tot.ah26win} maxHu=${tot.ah26huMax} 捉铳成交=${tot.pw}`);
fs.writeFileSync('_d39_out.txt', OUT.join('\n'), 'utf8');
console.log(OUT.join('\n'));
