// _d40.js — dealerPen 单测
const fs=require('fs'),path=require('path'),vm=require('vm');
let src=fs.readFileSync('measure_winrate.js','utf8').replace(/\nmain\(\);\s*$/,'\n').replace("'use strict';",'').replace(/\bconst /g,'var ');
globalThis.require=require;globalThis.__dirname=__dirname;globalThis.module={exports:{}};globalThis.process=process;
(0,eval)(src);
const loader=loadGameCode();
const {ctx,vmctx,taskQueue}=buildSandbox(20261027);
vm.runInContext('function __domStub(){ return __makeStub(); }',vmctx);
for(const c of loader.chunks){try{vm.runInContext(c,vmctx);}catch(e){console.log('装载失败',c.slice(0,40),e.message);}}
ctx.G.gameOver=false;ctx.G.aiLevel=3;
vm.runInContext(`
G.deck=generateDeck();G.deckCount=G.deck.length;
handCards=[];opponentHands[1]=[];opponentHands[2]=[];opponentMelds[1]=[];opponentMelds[2]=[];
for(let i=0;i<26;i++)handCards.push(parseDeckCard(G.deck.pop()));
for(let p=1;p<=2;p++)for(let i=0;i<25;i++){var s2=G.deck.pop();opponentHands[p].push(s2.indexOf(':')>=0?s2.substring(0,s2.indexOf(':')):s2);}
G.deckCount=G.deck.length;G._passRecord={};G._skippedOps={};G.dealerMelds=G.dealerMelds||[];
__lvCfg[0]=3;__lvCfg[1]=1;__lvCfg[2]=1;
handCards.push(makeCardData('孔'));handCards.push(makeCardData('孔'));
`,vmctx);
ctx.G.lastPlayedChar='孔';ctx.G.lastPlayedFrom=1;
try{ vm.runInContext('dealerPen()',vmctx); console.log('dealerPen OK'); }
catch(e){ console.log('dealerPen 抛错:', e.message); }
console.log('handCards=',ctx.handCards.length,'melds=',JSON.stringify(ctx.G.dealerMelds));
