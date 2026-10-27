// _d34.js — T9(上大人+乙乙) 逐步调试
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

const { ctx, vmctx } = buildSandbox(1);
vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
for (const chunk of loadGameCode().chunks) {
  try { vm.runInContext(chunk, vmctx); }
  catch (e) { console.log('装载失败:', chunk.slice(0, 60), '::', e.message); }
}

const dbg = `
(function(){
  var chs = ['上','大','人','乙','乙'];
  var cards = chs.map(c => makeCardData(c));
  var out = [];
  // 1) 常量检查
  out.push('MIN_HU=' + MIN_HU + '  ALL_SEQS含上大人=' + ALL_SEQS.some(s=>s.join('')==='上大人'));
  out.push('SEQ_BY_CHAR[上]=' + JSON.stringify((SEQ_BY_CHAR['上']||[]).map(s=>s.join(''))));
  // 2) 手动复现 trySingleEye：眼=乙乙
  var cc = {}; cards.filter(c=>!c.isWild).forEach(c=>{cc[c.ch]=(cc[c.ch]||0)+1;});
  out.push('cc=' + JSON.stringify(cc));
  var cnt = Object.assign({}, cc); cnt['乙'] -= 2; delete cnt['乙'];
  var eyeCards = cards.filter(c=>c.ch==='乙');
  var usedSet = new Set(eyeCards);
  var wcRem = [];
  var wu = [];
  var melds = [{type:'pair', chars:['乙','乙'], cards:eyeCards}];
  var results = [];
  var ok = _partition(cnt, wcRem, wu, cards.filter(c=>!c.isWild), melds, 0, usedSet, results);
  out.push('partition(上大人)=' + ok + ' results=' + results.length + ' melds=' + melds.map(m=>m.type+':'+m.cards.map(c=>c.ch).join('')).join('|'));
  // 3) 直接调 _analyzeHandCore 带 minHu=0
  var core = _analyzeHandCore(cards, [], 0);
  out.push('_analyzeHandCore(minHu=0)=' + (core ? JSON.stringify({isWin:core.isWin, hu:core.totalHu, melds:core.melds.map(m=>m.type+':'+m.cards.map(c=>c.ch).join('')).join('|')}) : 'null'));
  // 4) analyzeHandLoose
  var l = analyzeHandLoose(cards, []);
  out.push('analyzeHandLoose=' + (l ? JSON.stringify({isWin:l.isWin, hu:l.totalHu}) : 'null'));
  return out.join('\\n');
})()
`;
console.log(vm.runInContext(dbg, vmctx));
