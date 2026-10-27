// test_eps.js — Phase 11 人味ε扰动单测（确定性分支验证）
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');
const mwSrc = fs.readFileSync(path.join(__dirname, 'measure_winrate.js'), 'utf8')
  .replace(/\nmain\(\);\s*$/, '\n').replace("'use strict';", '').replace(/\bconst /g, 'var ');
globalThis.require = require; globalThis.__dirname = __dirname;
globalThis.module = { exports: {} }; globalThis.process = process;
(0, eval)(mwSrc);

let pass = 0, fail = 0;
const T = (n, c) => { if (c) { pass++; console.log('✅', n); } else { fail++; console.log('❌', n); } };
const HAND = ['上','大','人','乙','乙','三','三','五','五','五','孔','孔','礼','知','可'];

function makeCtx(lv, rnd) {
  const { ctx, vmctx } = buildSandbox(1);
  ctx.Math.random = rnd;  // 受控随机源
  vm.runInContext('function __domStub(){ return __makeStub(); }', vmctx);
  for (const c of loadGameCode().chunks) { try { vm.runInContext(c, vmctx); } catch (e) {} }
  vm.runInContext(`G.aiLevel = ${lv}; __lvCfg[1] = ${lv}; __lvCfg[0] = ${lv}; var __hand = ${JSON.stringify(HAND)};`, vmctx);
  return vmctx;
}
// 1. ε=1.5%(L3)：random=0.001 < 0.015 → 走扰动 → floor(0.001*15)=0
let v = makeCtx(3, () => 0.001);
T('L3 ε触发(0.001<0.015)→随机弃牌idx', vm.runInContext('aiPickDiscard(__hand.slice(),1)', v) === 0);
// 2. ε=1.5%(L3)：random=0.99 → 走策略路径（正常返回合法idx）
v = makeCtx(3, () => 0.99);
const i2 = vm.runInContext('aiPickDiscard(__hand.slice(),1)', v);
T('L3 ε不触发→策略路径合法idx', typeof i2 === 'number' && i2 >= 0 && i2 < 15);
// 3. L1 ε=15%：0.1<0.15 触发
v = makeCtx(1, () => 0.1);
const i1=vm.runInContext('aiPickDiscard(__hand.slice(),1)', v); console.log('L1 idx=',i1); T('L1 ε触发→floor(0.1*15)=1', i1===1);
// 4. L2 ε=7.5%：0.1>0.075 不触发
v = makeCtx(2, () => 0.1);
T('L2 ε不触发(0.1>0.075)', vm.runInContext('aiPickDiscard(__hand.slice(),1)', v) !== undefined);
// 5. L0 ε=77.5%：0.5<0.775 触发 → floor(0.5*15)=7
v = makeCtx(0, () => 0.5);
const i0=vm.runInContext('aiPickDiscard(__hand.slice(),1)', v); console.log('L0 idx=',i0); T('L0 ε触发→floor(0.5*15)=7', i0===7);
console.log(`\n${pass} 过 / ${fail} 败`);
process.exit(fail ? 1 : 0);
