// 精牌查表完整验证：红精(三五七)+黑精(乙九) × 对/坎/扎/招/穿/泛 全部可达组合
// 权威基准：精牌胡数速查表V3反馈版.docx + 计分引擎v3.py
// 约束：每种精牌最多3皮2花、赖子全局最多2张(仅配三五七)；黑精无赖子
const fs = require('fs')
const path = require('path');;
const vm = require('vm');
const core = fs.readFileSync(path.join(__dirname, 'hu_tests', 'hu_core_current.js'), 'utf8');
const sandbox = { console, Set, Object, Array, Math, Number, String, Date, JSON, parseInt, parseFloat, Infinity, NaN };
vm.createContext(sandbox);

// 构造测试代码：对每个组合调用 _calcMeld 验证
const testCode = `
(function(){
  const mk = makeCardData;
  // {type, mtype(查表用), isBlack, f, s, w, mainJinChar, not, main}
  const cases = [
    // ── 红精对（纯精查表 + 含赖逐张） ──
    {type:'pair', f:2,s:0,w:0, not:4,  main:8},
    {type:'pair', f:1,s:1,w:0, not:3,  main:6},
    {type:'pair', f:0,s:2,w:0, not:2,  main:4},
    {type:'pair', f:1,s:0,w:1, not:4,  main:8},   // 1花1赖（逐张）
    {type:'pair', f:0,s:1,w:1, not:3,  main:6},   // 1皮1赖（逐张）
    // ── 红精坎 ──
    {type:'kan', f:0,s:3,w:0, not:5,  main:10},
    {type:'kan', f:1,s:2,w:0, not:6,  main:12},
    {type:'kan', f:2,s:1,w:0, not:7,  main:14},
    {type:'kan', f:0,s:2,w:1, not:6,  main:12},
    {type:'kan', f:1,s:1,w:1, not:7,  main:14},
    {type:'kan', f:2,s:0,w:1, not:9,  main:18},
    {type:'kan', f:0,s:1,w:2, not:7,  main:14},
    {type:'kan', f:1,s:0,w:2, not:12, main:24},
    // ── 红精扎/招 ──
    {type:'zha', f:1,s:3,w:0, not:12, main:24},
    {type:'zha', f:2,s:2,w:0, not:14, main:28},
    {type:'zha', f:0,s:3,w:1, not:12, main:24},
    {type:'zha', f:1,s:2,w:1, not:14, main:28},
    {type:'zha', f:2,s:1,w:1, not:18, main:36},
    {type:'zha', f:0,s:2,w:2, not:14, main:28},
    {type:'zha', f:1,s:1,w:2, not:18, main:36},
    {type:'zha', f:2,s:0,w:2, not:24, main:48},
    // 招牌共用zha表
    {type:'zhao', f:1,s:3,w:0, not:12, main:24},
    {type:'zhao', f:2,s:2,w:0, not:14, main:28},
    // ── 红精穿/泛 ──
    {type:'chuan', f:2,s:3,w:0, not:28, main:56},
    {type:'chuan', f:1,s:3,w:1, not:28, main:56},
    {type:'chuan', f:0,s:3,w:2, not:28, main:56},
    {type:'chuan', f:2,s:2,w:1, not:36, main:72},
    {type:'chuan', f:1,s:2,w:2, not:36, main:72},
    {type:'chuan', f:2,s:1,w:2, not:48, main:96},
    {type:'fan',  f:2,s:3,w:0, not:28, main:56},  // 泛牌共用chuan表
    // ── 黑精对 ──
    {type:'pair', black:true, f:2,s:0,w:0, not:2, main:4},
    {type:'pair', black:true, f:1,s:1,w:0, not:1, main:2},
    {type:'pair', black:true, f:0,s:2,w:0, not:0, main:0},
    // ── 黑精坎 ──
    {type:'kan', black:true, f:2,s:1,w:0, not:3, main:6},
    {type:'kan', black:true, f:1,s:2,w:0, not:2, main:4},
    {type:'kan', black:true, f:0,s:3,w:0, not:1, main:2},
    // ── 黑精扎/招 ──
    {type:'zha', black:true, f:1,s:3,w:0, not:3, main:6},
    {type:'zha', black:true, f:2,s:2,w:0, not:4, main:8},
    // ── 黑精穿/泛 ──
    {type:'chuan', black:true, f:2,s:3,w:0, not:6, main:12},
  ];

  const out = [];
  for (const c of cases) {
    const baseCh = c.black ? '九' : '七';
    const cards = [];
    for (let i=0;i<c.f;i++) cards.push(mk(baseCh,'flower'));
    for (let i=0;i<c.s;i++) cards.push(mk(baseCh,'skin'));
    for (let i=0;i<c.w;i++) cards.push(mk('赖'));
    // 非主精: mainJinChar=null（主精不是该字，整手语境下 isMain=false 时主精字必不含该牌）
    const gotNot = _calcMeld(cards, c.type, false, null);
    const gotMain = _calcMeld(cards, c.type, true, baseCh);
    const label = (c.black?'黑':'红') + '精' + c.type + '(' + c.f + '花' + c.s + '皮' + c.w + '赖)';
    out.push({label, gotNot, gotMain, expNot:c.not, expMain:c.main,
      okNot: gotNot === c.not, okMain: gotMain === c.main});
  }
  return out;
})()
`;
const res = JSON.parse(vm.runInContext(core + '\n' + 'JSON.stringify(' + testCode + ')', sandbox));

let all = true;
let fail = 0;
for (const r of res) {
  const ok = r.okNot && r.okMain;
  if (!ok) { all = false; fail++; }
  console.log((ok ? '✅' : '❌') + ' ' + r.label + '  非主精:' + r.gotNot + '(期望' + r.expNot + ') 主精:' + r.gotMain + '(期望' + r.expMain + ')');
}
console.log('\n共 ' + res.length + ' 项，失败 ' + fail + ' 项');
console.log(all ? '精牌查表全部验证通过 ✅' : '存在失败 ❌');
