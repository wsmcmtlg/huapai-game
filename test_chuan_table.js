// 表驱动验证：红精穿牌 6 种可达组合查表全部命中且值正确
const fs = require('fs')
const path = require('path');;
const vm = require('vm');
const core = fs.readFileSync(path.join(__dirname, 'hu_tests', 'hu_core_current.js'), 'utf8');
const sandbox = { console, Set, Object, Array, Math, Number, String, Date, JSON, parseInt, parseFloat, Infinity, NaN };
vm.createContext(sandbox);
const testCode = `
(function(){
  const mk = makeCardData;
  const cases = [
    {f:0, s:3, w:2, expect:56},
    {f:1, s:3, w:1, expect:56},
    {f:2, s:3, w:0, expect:56},
    {f:1, s:2, w:2, expect:72},
    {f:2, s:2, w:1, expect:72},
    {f:2, s:1, w:2, expect:96},
  ];
  const out = [];
  for (const c of cases) {
    const cards = [];
    for (let i=0;i<c.f;i++) cards.push(mk('七','flower'));
    for (let i=0;i<c.s;i++) cards.push(mk('七','skin'));
    for (let i=0;i<c.w;i++) cards.push(mk('赖'));
    const huMain = _calcMeld(cards, 'chuan', true, '七');
    const huNot = _calcMeld(cards, 'chuan', false, '七');
    const key = c.f + '_' + c.s + '_' + c.w;
    out.push({key, huMain, huNot, expectMain:c.expect, expectNot:c.expect/2,
      mainOK: huMain === c.expect, notOK: huNot === c.expect/2});
  }
  return out;
})()
`;
const res = JSON.parse(vm.runInContext(core + '\n' + 'JSON.stringify(' + testCode + ')', sandbox));
let all = true;
for (const r of res) {
  const ok = r.mainOK && r.notOK;
  if (!ok) all = false;
  console.log('key=' + r.key + ' 主精:' + r.huMain + '(期望' + r.expectMain + ') 非主精:' + r.huNot + '(期望' + r.expectNot + ') ' + (ok ? '✅' : '❌'));
}
console.log(all ? '\n红精穿牌表全部6条验证通过 ✅' : '\n存在失败 ❌');
