// _d35.js — 轮转跟踪：庄家回合为何几乎不被驱动
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

const { ctx, vmctx, taskQueue } = buildSandbox(20261027);
vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
for (const chunk of loadGameCode().chunks) {
  try { vm.runInContext(chunk, vmctx); }
  catch (e) { console.log('装载失败:', chunk.slice(0, 60), '::', e.message); }
}

ctx.G.gameOver = false; ctx.G.aiLevel = 3;
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

const trace = [];
let dealerTurns = 0, steps = 0;
const MAX_STEPS = 20000;

const runDealerTurn = (first) => {
  dealerTurns++;
  trace.push(`[step${steps}] 庄家回合#${dealerTurns} deck=${ctx.G.deckCount} 庄=${ctx.handCards.length} 下=${ctx.opponentHands[1].length} 上=${ctx.opponentHands[2].length}`);
  if (!first) {
    if (ctx.G.deckCount > 0) {
      const s = ctx.G.deck.pop(); ctx.handCards.push(s.indexOf(':') >= 0 ? s.substring(0, s.indexOf(':')) : s);
      ctx.G.deckCount--;
    } else { ctx.__winner = 'draw'; ctx.G.gameOver = true; trace.push('  → 牌墙耗尽，荒庄'); return; }
  }
  ctx.G.aiLevel = 3;
  const hu = vm.runInContext('analyzeHand(handCards.map(c => makeCardData(c)))', vmctx);
  if (hu && hu.isWin) { ctx.__winner = 'win:0:' + (hu.totalHu || 0); ctx.G.gameOver = true; trace.push('  → 庄家胡 ' + hu.totalHu); return; }
  const idx = vm.runInContext('aiPickDiscard(handCards, 0)', vmctx);
  if (typeof idx !== 'number' || idx < 0 || idx >= ctx.handCards.length) { ctx.__winner = 'draw'; ctx.G.gameOver = true; trace.push('  → aiPickDiscard 非法: ' + idx); return; }
  const played = ctx.handCards.splice(idx, 1)[0];
  ctx.G.lastPlayedChar = played; ctx.G.lastPlayedFrom = 0;
  trace.push(`  → 庄出 ${played}，入队 checkResponseAfterOpponent(0)`);
  taskQueue.push(() => { try { vm.runInContext('checkResponseAfterOpponent(0)', vmctx); } catch (e) { ctx.__winner = 'draw'; ctx.G.gameOver = true; trace.push('  → 响应链异常: ' + e.message); } });
};
taskQueue.push(() => runDealerTurn(true));

while (!ctx.G.gameOver && steps++ < MAX_STEPS) {
  if (taskQueue.length) {
    const fn = taskQueue.shift();
    const before = taskQueue.length;
    try { fn(); }
    catch (e) {
      const msg = e && e.message || '';
      if (/querySelector|innerHTML|classList|style|appendChild|textContent/.test(msg)) continue;
      trace.push(`[step${steps}] 队列任务异常: ${msg.slice(0, 100)}`); ctx.G.gameOver = true;
    }
    if (steps <= 40) trace.push(`[step${steps}] 队列任务执行后 新任务=${taskQueue.length - before} 现有=${taskQueue.length} deck=${ctx.G.deckCount} cp=${ctx.G.currentPlayer}`);
  }
  else { runDealerTurn(); }
}
trace.push(`结果: ${ctx.__winner} 庄家回合数=${dealerTurns} 总步数=${steps}`);
fs.writeFileSync('_trace_out.txt', trace.join('\n'), 'utf8');
console.log(trace.slice(0, 50).join('\n'));
console.log('...');
console.log('完整输出在 _trace_out.txt，共', trace.length, '行');
