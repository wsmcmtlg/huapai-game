// test_profile.js — Phase 10 跨局建模单测（mock localStorage）
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');
// 读取 measure 的沙箱基建
const mwSrc = fs.readFileSync(path.join(__dirname, 'measure_winrate.js'), 'utf8')
  .replace(/\nmain\(\);\s*$/, '\n').replace("'use strict';", '').replace(/\bconst /g, 'var ');
globalThis.require = require; globalThis.__dirname = __dirname;
globalThis.module = { exports: {} }; globalThis.process = process;
(0, eval)(mwSrc);

let pass = 0, fail = 0;
const T = (name, cond) => { if (cond) { pass++; console.log('✅', name); } else { fail++; console.log('❌', name); } };

// mock localStorage
const store = {};
const { ctx, vmctx } = buildSandbox(1);
ctx.localStorage = { getItem: k => store[k] !== undefined ? store[k] : null, setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; } };
vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
for (const c of loadGameCode().chunks) { try { vm.runInContext(c, vmctx); } catch (e) { console.log('装载失败', e.message); } }

// 1. 档案读写回路
vm.runInContext(`_profRecord(0,'zha','三'); _profRecord(0,'zha','三'); _profRecord(0,'pen','孔'); _profRecord(0,'discard','上'); _profRecord(1,'zha','五'); _profGameDone(); _profGameDone(); _profGameDone();`, vmctx);
const p = JSON.parse(store['hp_profile_v1']);
T('扎牌计数跨局保存', p.zha['三'] === 2);
T('碰牌计数', p.pen['孔'] === 1);
T('出牌习惯', p.disc['上'] === 1);
T('旁家行为不入档（只记人类位0）', p.zha['五'] === undefined);
T('局数累计', p.games === 3);

// 2. 档案不足3局不启用 → 逻辑字段
T('games>=3 启用阈值', (p.games >= 3) === true);

// 3. 损坏档案容错
store['hp_profile_v1'] = '{broken json';
const p2 = vm.runInContext('_profLoad()', vmctx);
T('损坏档案返回null不炸', p2 === null);

// 4. L3 使用点不炸（带档案跑一次 L3 决策）
vm.runInContext(`_profRecord(0,'zha','五'); _profRecord(0,'pen','五'); _profRecord(0,'discard','乙');`, vmctx);
const idx = vm.runInContext(`(function(){ var hand=['上','大','人','乙','乙','三','三','五','五','五','孔','孔','礼','知','可']; var i=aiPickDiscard(hand,1); return typeof i; })()`, vmctx);
T('带档案L3出牌决策正常', idx === 'number');

// 5. 空档案（localStorage null）也不炸
delete store['hp_profile_v1'];
const idx2 = vm.runInContext(`(function(){ var hand=['上','大','人','乙','乙','三','三','五','五','五','孔','孔','礼','知','可']; var i=aiPickDiscard(hand,1); return typeof i; })()`, vmctx);
T('空档案L3决策正常', idx2 === 'number');

console.log(`\n${pass} 过 / ${fail} 败`);
process.exit(fail ? 1 : 0);
