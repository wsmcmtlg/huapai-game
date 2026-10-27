const fs=require('fs'),path=require('path'),vm=require('vm');
let src=fs.readFileSync('measure_winrate.js','utf8').replace(/\nmain\(\);\s*$/,'\n').replace("'use strict';",'').replace(/\bconst /g,'var ');
globalThis.require=require;globalThis.__dirname=__dirname;globalThis.module={exports:{}};globalThis.process=process;
(0,eval)(src);
const probe=`
;var __c = { cra: 0, craCh: {}, pairSeen: 0, lpf: {} };
var __ocr = checkResponseAfterOpponent;
checkResponseAfterOpponent = function(fi) {
  __c.cra++;
  var ch = G.lastPlayedChar;
  if (ch) { __c.craCh[ch] = (__c.craCh[ch]||0)+1;
    var cnt = 0; for (var i=0;i<handCards.length;i++) if (handCards[i].ch===ch) cnt++;
    if (G.drawnCard && G.drawnCard.ch===ch) cnt++;
    if (cnt>=2) __c.pairSeen++;
    __c.lpf[fi] = (__c.lpf[fi]||0)+1;
  }
  return __ocr(fi);
};
`;
for(let g=0; g<10; g++){
  const r = runOneGame(loadGameCode(), [3,1,1], 20261027+g*7919);
  // probe 需要在 runOneGame 内注入——改为手动跑一局
  break;
}
// 手动跑
const {ctx,vmctx,taskQueue}=buildSandbox(20261027);
vm.runInContext('function __domStub(){ return __makeStub(); }',vmctx);
for(const c of loadGameCode().chunks.concat([probe])){try{vm.runInContext(c,vmctx);}catch(e){console.log('装载失败',e.message);}}
ctx.G.gameOver=false;ctx.G.aiLevel=3;
vm.runInContext(`
G.deck=generateDeck();G.deckCount=G.deck.length;
handCards=[];opponentHands[1]=[];opponentHands[2]=[];opponentMelds[1]=[];opponentMelds[2]=[];
for(let i=0;i<26;i++)handCards.push(parseDeckCard(G.deck.pop()));
for(let p=1;p<=2;p++)for(let i=0;i<25;i++){var s2=G.deck.pop();opponentHands[p].push(s2.indexOf(':')>=0?s2.substring(0,s2.indexOf(':')):s2);}
G.deckCount=G.deck.length;G._passRecord={};G._skippedOps={};G.dealerMelds=G.dealerMelds||[];
__lvCfg[0]=3;__lvCfg[1]=1;__lvCfg[2]=1;
`,vmctx);
let turns=0;
const runDealerTurn=(first)=>{
  turns++;
  if(!first){ if(ctx.G.deckCount>0){const cd=vm.runInContext('parseDeckCard(G.deck.pop())',vmctx);ctx.handCards.push(cd);ctx.G.deckCount--;ctx.G.drawnCard=cd;} else {ctx.__winner='draw';ctx.G.gameOver=true;return;} }
  ctx.G.aiLevel=3;
  const hu=vm.runInContext('analyzeHand(handCards.slice())',vmctx);
  if(hu&&hu.isWin){ctx.__winner='win:0:'+hu.totalHu;ctx.G.gameOver=true;return;}
  const idx=vm.runInContext('aiPickDiscard(handCards,0)',vmctx);
  if(typeof idx!=='number'||idx<0||idx>=ctx.handCards.length){ctx.__winner='draw';ctx.G.gameOver=true;return;}
  const played=ctx.handCards.splice(idx,1)[0];
  ctx.G.lastPlayedChar=played.ch!==undefined?played.ch:played;ctx.G.lastPlayedFrom=0;ctx.G.drawnCard=null;
  taskQueue.push(()=>{try{vm.runInContext('checkResponseAfterOpponent(0)',vmctx);}catch(e){const m=e.message||'';if(!/querySelector|innerHTML|classList|style|appendChild|textContent/.test(m)){ctx.__winner='draw';ctx.G.gameOver=true;}}});
};
taskQueue.push(()=>runDealerTurn(true));
let guard=0;
while(!ctx.G.gameOver&&guard++<20000){
  if(taskQueue.length){const fn=taskQueue.shift();try{fn();}catch(e){const m=e&&e.message||'';if(!/querySelector|innerHTML|classList|style|appendChild|textContent/.test(m)){ctx.__err=m;ctx.G.gameOver=true;}}}
  else runDealerTurn();
}
console.log('结果',ctx.__winner,'err',ctx.__err||'-','turns',turns);
console.log(JSON.stringify(ctx.__c));
