// 核对：黑精牌型在整手分析中永不为主精（乙九不能当主精），恒按非主精计胡
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const core = fs.readFileSync(path.join(__dirname, 'hu_core_current.js'), 'utf8');
const sandbox = { console, Set, Object, Array, Math, Number, String, Date, JSON, parseInt, parseFloat, Infinity, NaN };
vm.createContext(sandbox);
const code = core + `
(function(){
  const mk = makeCardData;
  // 黑精牌型：乙九字面，不含红精主精(三五七)
  const bkan = [mk('九','flower'),mk('九','flower'),mk('九','skin')];      // 1皮2花
  const bzha = [mk('九','skin'),mk('九','skin'),mk('九','flower'),mk('九','flower')]; // 2皮2花
  const bchuan= [mk('九','skin'),mk('九','skin'),mk('九','skin'),mk('九','flower'),mk('九','flower')]; // 3皮2花
  const out = {};
  // 模拟整手主精=七：黑精牌型 isMain 判定
  out.bkan_handMainQi = _calcMeld(bkan,'kan', true, '七');   // 手动传isMain=true模拟错误情形
  out.bkan_norm      = _calcMeld(bkan,'kan', false, '七');   // 正常：isMain=false
  out.bzha_handMainQi= _calcMeld(bzha,'zha', true, '七');
  out.bzha_norm      = _calcMeld(bzha,'zha', false, '七');
  out.bchuan_handMainQi=_calcMeld(bchuan,'chuan', true, '七');
  out.bchuan_norm    = _calcMeld(bchuan,'chuan', false, '七');
  // 整手场景：构造含黑精牌型 + 主精=七 的总胡（验证黑精项不翻倍）
  const melds = [
    {type:'kan', chars:['九','九','九'], cards:bkan},
    {type:'zha', chars:['九','九','九','九'], cards:bzha},
    {type:'chuan', chars:['九','九','九','九','九'], cards:bchuan},
  ];
  const det = _calcTotalHu(melds, '七');
  out.handTotal_breakdown = det.breakdown.map(b => b.label+'='+b.hu).join(' | ');
  out.handTotal = det.total;
  return out;
})()
`;
console.log(JSON.stringify(vm.runInContext(code, sandbox), null, 1));
