const fs=require('fs'),path=require('path'),vm=require('vm');
let src=fs.readFileSync('measure_winrate.js','utf8').replace(/\nmain\(\);\s*$/,'\n').replace("'use strict';",'').replace(/\bconst /g,'var ');
globalThis.require=require;globalThis.__dirname=__dirname;globalThis.module={exports:{}};globalThis.process=process;
(0,eval)(src);
const {ctx,vmctx,taskQueue}=buildSandbox(20261027);
vm.runInContext('function __domStub(){ return __makeStub(); }',vmctx);
for(const c of loadGameCode().chunks){try{vm.runInContext(c,vmctx);}catch(e){}}
ctx.G.gameOver=false;ctx.G.aiLevel=3;
vm.runInContext(`
G.deck=generateDeck();G.deckCount=G.deck.length;
handCards=[];opponentHands[1]=[];opponentHands[2]=[];opponentMelds[1]=[];opponentMelds[2]=[];
for(let i=0;i<26;i++)handCards.push(parseDeckCard(G.deck.pop()));
for(let p=1;p<=2;p++)for(let i=0;i<25;i++){var s2=G.deck.pop();opponentHands[p].push(s2.indexOf(':')>=0?s2.substring(0,s2.indexOf(':')):s2);}
G.deckCount=G.deck.length;G._passRecord={};G._skippedOps={};G.dealerMelds=G.dealerMelds||[];
__lvCfg[0]=3;__lvCfg[1]=1;__lvCfg[2]=1;
`,vmctx);
const preM = vm.runInContext(`(function(){
  window.__pm = function(){
    return (G.dealerMelds||[]).map(function(m){
      if (m.inHand) { var cards = m.cards || Array.from({length:4}, function(){ return makeCardData(m.char); }); return {type:'zha', chars:cards.map(function(c){return c.ch;}), cards:cards.slice(0,4)}; }
      var cards2 = m.cards || Array.from({length:m.count}, function(){ return makeCardData(m.char); });
      return {type: m.type || 'pen', chars: Array(m.count).fill(m.char), cards: cards2};
    });
  };
})()`, vmctx);
const pm = () => vm.runInContext('__pm()', vmctx);
let turns=0, claims=0;
const dlog=[];
const runDealerTurn=(first)=>{
  turns++;
  if(!first){ if(ctx.G.deckCount>0){const cd=vm.runInContext('parseDeckCard(G.deck.pop())',vmctx);ctx.handCards.push(cd);ctx.G.deckCount--;ctx.G.drawnCard=cd;} else {ctx.__winner='draw';ctx.G.gameOver=true;return;} }
  ctx.G.aiLevel=3;
  const st = vm.runInContext('(function(){var l=analyzeHandLoose(handCards.slice(), __pm()); return l? {hu:l.totalHu,win:l.isWin} : null;})()',vmctx);
  const hu=vm.runInContext('analyzeHand(handCards.slice(), __pm())',vmctx);
  dlog.push(`t${turns} 手=${ctx.handCards.length} 明=${ctx.G.dealerMelds.length} loose=${st?JSON.stringify(st):'null'} strictWin=${hu&&hu.isWin?hu.totalHu:'-'}`);
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
  else {
    if(ctx.G._pendingWin){ctx.__winner='win:0:'+(ctx.G._pendingWin.totalHu||0);ctx.G.gameOver=true;ctx.G._pendingWin=null;}
    else if(ctx.G.lastPlayedChar&&ctx.G.lastPlayedFrom!==0){
      const claim=vm.runInContext(`(function(){var ch=G.lastPlayedChar;if(!ch)return null;var cnt=0;for(var i=0;i<handCards.length;i++)if(handCards[i].ch===ch)cnt++;if(G.drawnCard&&G.drawnCard.ch===ch)cnt++;var penCnt=0;for(var j=0;j<G.dealerMelds.length;j++)if(G.dealerMelds[j].type==='pen')penCnt++;if(cnt>=3&&!G._skippedOps['zhao_'+ch])return 'zhao';if(cnt>=2&&penCnt<2&&!G._skippedOps['pen_'+ch])return 'pen';return null;})()`,vmctx);
      if(claim){claims++;try{vm.runInContext(claim==='zhao'?'dealerZhao()':'dealerPen()',vmctx);}catch(e){const m=e.message||'';if(!/querySelector|innerHTML|classList|style|appendChild|textContent|removeChild|parentNode/.test(m)){ctx.__err='claim:'+m;ctx.G.gameOver=true;}}
        if(!ctx.G.gameOver){
          const idx2=vm.runInContext('aiPickDiscard(handCards,0)',vmctx);
          if(typeof idx2==='number'&&idx2>=0&&idx2<ctx.handCards.length){const p2=ctx.handCards.splice(idx2,1)[0];ctx.G.lastPlayedChar=p2.ch!==undefined?p2.ch:p2;ctx.G.lastPlayedFrom=0;ctx.G.drawnCard=null;
            taskQueue.push(()=>{try{vm.runInContext('checkResponseAfterOpponent(0)',vmctx);}catch(e){const m=e.message||'';if(!/querySelector|innerHTML|classList|style|appendChild|textContent/.test(m)){ctx.__winner='draw';ctx.G.gameOver=true;}}});
          } else {ctx.__winner='draw';ctx.G.gameOver=true;}
        }
      } else runDealerTurn();
    } else runDealerTurn();
  }
}
console.log('结果',ctx.__winner,'err',ctx.__err||'-','turns',turns,'claims',claims);
console.log(dlog.join('\n'));
