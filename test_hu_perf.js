// 性能对比：修复前后 analyzeHand 耗时（含新增重分配枚举）
const fs = require('fs')
const path = require('path');;
const vm = require('vm');

function makeEval(corePath) {
  const core = fs.readFileSync(corePath, 'utf8');
  return function(code) {
    const sandbox = { console, Set, Object, Array, Math, Number, String, Date, JSON, parseInt, parseFloat, Infinity, NaN, performance };
    vm.createContext(sandbox);
    return JSON.parse(vm.runInContext(core + '\n' + 'JSON.stringify((function(){' + code + '})())', sandbox));
  };
}

const mk = (desc) => {
  const [ch, v] = desc.split(':');
  if (ch === '赖') return `mk('赖')`;
  return v ? `mk('${ch}','${v === 'f' ? 'flower' : 'skin'}')` : `mk('${ch}')`;
};
const meld = (type, descs) => ({ type, chars: descs.map(d => d.split(':')[0]), cards: descs.map(mk) });

const commonOther = ['可', '知', '礼', '三:s', '四', '五:f', '八', '九:s', '子', '八', '九:s', '十'];

// 多个含穿牌/扎牌的牌组场景（含赖子通配、多穿牌等）
const scenarios = [
  // 用户场景
  { preMelds: [meld('chuan', ['七:s','七:f','七:s','七:s','赖']), meld('zha',['土','土','土','土']), meld('zhao',['上','上','上','上']), meld('pen',['化','化','化'])], cards: ['七:f','土', ...commonOther] },
  // 穿牌含2赖
  { preMelds: [meld('chuan', ['七:f','七:s','七:s','赖','赖']), meld('zha',['土','土','土','土']), meld('zhao',['上','上','上','上']), meld('pen',['化','化','化'])], cards: ['七:f','土', ...commonOther] },
  // 泛牌
  { preMelds: [meld('fan', ['七:s','七:f','七:s','七:s','赖']), meld('zha',['土','土','土','土']), meld('zhao',['上','上','上','上']), meld('pen',['化','化','化'])], cards: ['七:f','土', ...commonOther] },
  // 扎牌(1花2皮1赖)
  { preMelds: [meld('zha', ['七:f','七:s','七:s','赖']), meld('zhao',['上','上','上','上']), meld('pen',['化','化','化'])], cards: ['七:f','土', ...commonOther] },
  // 无扩展牌型
  { preMelds: [], cards: ['七:f','土', ...commonOther] },
];

function bench(corePath, label) {
  const ev = makeEval(corePath);
  const timings = [];
  for (const sc of scenarios) {
    const code = `
      const mk = makeCardData;
      const preMelds = ${JSON.stringify(sc.preMelds).replace(/"mk\(([^)]*)\)"/g, 'mk($1)')};
      const cards = ${JSON.stringify(sc.cards.map(mk)).replace(/"mk\(([^)]*)\)"/g, 'mk($1)')};
      const N = 500;
      let t0 = performance.now();
      let last = null;
      for (let i = 0; i < N; i++) { last = analyzeHand(cards, preMelds); }
      let t1 = performance.now();
      let hu = last ? _calcTotalHu(last.melds, last.mainJin).total : -1;
      return {msPerCall: (t1 - t0) / N, hu};
    `;
    const r = ev(code);
    timings.push(r);
  }
  console.log('==== ' + label + ' ====');
  let total = 0;
  timings.forEach((t, i) => { total += t.msPerCall; console.log('  场景' + (i + 1) + ': ' + t.msPerCall.toFixed(3) + ' ms/次, hu=' + t.hu); });
  console.log('  平均: ' + (total / timings.length).toFixed(3) + ' ms/次');
  return total / timings.length;
}

const beforeAvg = bench(path.join(__dirname, 'hu_tests', 'hu_core_before.js'), '修复前');
const afterAvg = bench(path.join(__dirname, 'hu_tests', 'hu_core_current.js'), '修复后');
console.log('\n对比: 修复后平均耗时 ' + afterAvg.toFixed(3) + 'ms vs 修复前 ' + beforeAvg.toFixed(3) + 'ms, 增量 ' + (afterAvg - beforeAvg).toFixed(3) + 'ms');
console.log('结论: ' + (afterAvg < 120 ? '在120ms AI预算内 ✅' : '超预算 ❌'));
