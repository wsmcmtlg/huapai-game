// _d33.js — 最小用例：analyzeHand / analyzeHandLoose 行为验证
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

const mk = chs => `(${JSON.stringify(chs)}).map(c => makeCardData(c))`;
const tests = [
  // 名, 手牌
  ['T1 双精坎+眼(应胡30)', ['三','三','三','五','五','五','上','上']],
  ['T2 红精坎+固定顺+眼(15+1, 结构完整但<17)', ['三','三','三','上','大','人','乙','乙']],
  ['T3 4副+1眼(结构完整, 胡数看构成)', ['上','大','人','可','知','礼','乙','二','三','四','五','六','七','八','九','十','三','三','化','化']],
  ['T4 单坎赖子', ['赖','三','三','五','五','五','上','上']],
  ['T5 黑精不顶用', ['乙','乙','乙','九','九','九','上','上']],
  ['T6 坎+顺+人眼', ['三','三','三','上','大','人','人','人']],
  ['T7 坎+数字顺+对', ['三','三','三','乙','二','三','上','上']],
  ['T8 纯固定顺+对', ['上','大','人','可','知','礼','乙','乙']],
  ['T9 单顺+对(最小结构)', ['上','大','人','乙','乙']],
  ['T10 单坎+对', ['三','三','三','乙','乙']],
  ['T11 黑精坎+人眼', ['乙','乙','乙','人','人']],
];
for (const [name, chs] of tests) {
  const src = `
    (function(){
      var cards = ${mk(chs)};
      var a = analyzeHand(cards);
      var l = analyzeHandLoose(cards);
      return JSON.stringify({ hand: ${JSON.stringify(chs.join(''))},
        A: a ? {isWin:a.isWin, hu:a.totalHu, melds:(a.melds||[]).map(m=>m.type+':'+m.cards.map(c=>c.ch).join('')).join('|')} : null,
        L: l ? {isWin:l.isWin, hu:l.totalHu, melds:(l.melds||[]).map(m=>m.type+':'+m.cards.map(c=>c.ch).join('')).join('|')} : null });
    })()
  `;
  console.log(name, '→', vm.runInContext(src, vmctx));
}
