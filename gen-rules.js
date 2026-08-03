const path = require('path');
const h = require(path.join(process.env.SKILL_PATH, 'docx', 'scripts', 'docx-helper'))({
  fonts: { heading: 'SimHei', body: 'SimSun' },
  colors: { primary: '1a472a', text: '333333', light: 'EDF5EE' },
  page: { width: 11906, height: 16838 },
  sizes: { h1: 32, h2: 28, h3: 24, body: 21 },
  indent: { firstLine: 420 },
});

const C = h.colors;
const refs = h.refTracker();
const hf = h.headerFooter('花牌计胡规则确认表');

// 添加"确认"列的工具函数
const COL = { Y: 1200, LABEL: 2600, DETAIL: 4600 };
function checkTable(spec) {
  const widths = [...spec.widths, COL.Y];
  const header = [...spec.header, '确认'];
  const rows = spec.rows.map(r => [...r, '□ 是 / □ 否']);
  return h.table({ widths, header, rows, headerColor: '1a472a', altColor: 'EDF5EE', noBorders: true });
}

// 封面
function coverSection() {
  return [
    h.spacer(3000),
    h.p('公安花牌', { size: 56, bold: true, color: 'FFFFFF', align: 'center' }),
    h.spacer(200),
    h.p('计胡规则确认表', { size: 32, color: 'D4E8D4', align: 'center' }),
    h.spacer(400),
    h.p('逐项确认规则是否全面准确', { size: 22, color: 'A0C4A0', align: 'center' }),
    h.spacer(3000),
    h.p('版本 1.0', { size: 20, color: 'C0D8C0', align: 'center' }),
    h.p('2026-07-29', { size: 20, color: 'C0D8C0', align: 'center' }),
  ];
}

// ─── 一、牌型基础 ───
function section1() {
  return [
    h.h1('一、牌型基础'),
    h.h2('1.1 字符分类'),
    checkTable({
      widths: [COL.LABEL, COL.DETAIL],
      header: ['分类', '字符'],
      rows: [
        ['红字', '上大人可知礼三五七赖'],
        ['黑字', '化千孔乙己七十土八九十二四六八十'],
        ['红精', '三五七（红色精牌）'],
        ['黑精', '乙九（黑色精牌）'],
        ['赖子', '赖（通配符，仅可通配三五七）'],
      ],
    }),
    h.h2('1.2 牌的花/皮'),
    checkTable({
      widths: [COL.LABEL, COL.DETAIL],
      header: ['类型', '说明'],
      rows: [
        ['花精', '每精牌字 2 张，大写显示（叁/伍/柒/壹/玖）'],
        ['皮精', '每精牌字 3 张，原字显示（三/五/七/乙/九）'],
        ['非精牌', '均为皮，每字 5 张'],
      ],
    }),
    h.h2('1.3 合法顺子（14 种）'),
    h.p('固定顺子（6 种）：上大人、可知礼、化三千、孔乙己、七十土、八九子', { indent: { firstLine: 0 } }),
    h.p('数字顺子（8 种）：乙二三、二三四、三四五、四五六、五六七、六七八、七八九、八九十', { indent: { firstLine: 0 } }),
    h.h2('1.4 合法口眼（半顺子）'),
    h.p('从 14 种顺子中各取任意 2 个字符组成，共 C(3,2) × 14 = 42 种。例如：上大（缺人）、三四（缺五）、八九（缺子）等。'),
    h.p('确认：□ 是 / □ 否', { indent: { firstLine: 0 }, color: '888888' }),
  ];
}

// ─── 二、计胡规则 ───
function section2() {
  return [
    h.h1('二、计胡规则（按牌型）'),
    h.h2('2.1 pair（对子眼）'),
    h.p('定义：2 张同字符作为胡牌的眼。仅计精牌部分，非精牌不计。主精逐张翻倍。'),
    checkTable({
      widths: [COL.LABEL, COL.DETAIL],
      header: ['成分', '单张计胡'],
      rows: [
        ['非精牌', '0 胡（皮乙九、皮三五七不计）'],
        ['皮三五七', '+1 胡'],
        ['花三五七', '+2 胡'],
        ['皮乙九', '0 胡'],
        ['花乙九', '+1 胡'],
        ['赖子', '+2 胡（最低当花精计）'],
        ['主精翻倍', '仅翻该张牌，非总和翻倍'],
      ],
    }),
    h.p('示例：花三(2胡) + 皮三(1胡)，三为主精 → 2×2 + 1×2 = 6胡'),
    h.p('确认：□ 是 / □ 否', { indent: { firstLine: 0 }, color: '888888' }),

    h.h2('2.2 kou（口眼，半顺子）'),
    h.p('定义：顺子缺 1 字作为眼，如"上大"缺"人"。仅计精牌部分，主精逐张翻倍。'),
    checkTable({
      widths: [COL.LABEL, COL.DETAIL],
      header: ['成分', '单张计胡'],
      rows: [
        ['皮三五七', '+1 胡'],
        ['花三五七', '+2 胡'],
        ['皮乙九', '0 胡'],
        ['花乙九', '+1 胡'],
        ['赖子替代精牌', '+2 胡'],
        ['主精翻倍', '该张 ×2'],
      ],
    }),
    h.p('确认：□ 是 / □ 否', { indent: { firstLine: 0 }, color: '888888' }),

    h.h2('2.3 seq（顺子）'),
    h.p('定义：3 张合法顺子。计胡公式：base + Σ(精牌计胡)。主精逐张翻倍。'),
    checkTable({
      widths: [COL.LABEL, COL.DETAIL],
      header: ['成分', '计胡'],
      rows: [
        ['base（红顺子：上大人、可知礼）', '+1 胡'],
        ['base（其他顺子）', '0 胡'],
        ['皮三五七', '+1 胡'],
        ['花三五七', '+2 胡'],
        ['皮乙九', '0 胡'],
        ['花乙九', '+1 胡'],
        ['赖子替代精牌', '+2 胡'],
        ['主精翻倍', '该张 ×2'],
      ],
    }),
    h.p('确认：□ 是 / □ 否', { indent: { firstLine: 0 }, color: '888888' }),

    h.h2('2.4 kan（坎牌）'),
    h.p('定义：3 张同字符。先查精牌表，未命中则兜底逐张计。主精逐张翻倍。'),
    checkTable({
      widths: [COL.LABEL, COL.DETAIL],
      header: ['成分', '计胡'],
      rows: [
        ['无精 base（全红字）', '2 胡'],
        ['无精 base（含黑字）', '1 胡'],
        ['皮三五七', '+1 胡/张'],
        ['花三五七', '+2 胡/张'],
        ['皮乙九', '0 胡/张'],
        ['花乙九', '+1 胡/张'],
        ['赖子', '+2 胡'],
        ['主精翻倍', '该张 ×2'],
      ],
    }),
    h.h3('红精坎查表（主精 ×2）'),
    checkTable({
      widths: [COL.LABEL, COL.DETAIL],
      header: ['花_皮_赖', '胡数（主精翻倍）'],
      rows: [
        ['2_0_0', '4（主精 8）'],
        ['1_1_0', '3（主精 6）'],
        ['0_2_0', '2（主精 4）'],
        ['1_0_2', '12（主精 24）'],
        ['2_0_1', '9（主精 18）'],
        ['0_1_2', '7（主精 14）'],
        ['1_1_1', '7（主精 14）'],
        ['0_2_1', '6（主精 12）'],
      ],
    }),
    h.p('确认：□ 是 / □ 否', { indent: { firstLine: 0 }, color: '888888' }),

    h.h2('2.5 pen（碰牌）'),
    h.p('定义：旁家出牌后，手中 2 张同字组成 3 张明牌。主精逐张翻倍。'),
    checkTable({
      widths: [COL.LABEL, COL.DETAIL],
      header: ['成分', '红碰', '黑碰'],
      rows: [
        ['base', '1 胡', '0 胡'],
        ['皮三五七', '+1 胡/张', '+1 胡/张'],
        ['花三五七', '+2 胡/张', '+2 胡/张'],
        ['皮乙九', '0 胡', '0 胡'],
        ['花乙九', '+1 胡', '+1 胡'],
        ['赖子', '+2 胡', '+2 胡'],
        ['主精翻倍', '该张 ×2', '该张 ×2'],
      ],
    }),
    h.p('确认：□ 是 / □ 否', { indent: { firstLine: 0 }, color: '888888' }),

    h.h2('2.6 zhao/zha（招牌/扎牌）'),
    h.p('定义：4 张同字符。招牌为已有坎牌 + 旁家打出第 4 张；扎牌为手牌中 4 张同字。先查精牌表（共用 zhao 表），未命中则兜底。'),
    checkTable({
      widths: [COL.LABEL, COL.DETAIL],
      header: ['成分', '全红', '含黑'],
      rows: [
        ['无精 base', '4 胡', '2 胡'],
        ['精牌/赖子', '查表或逐张', '查表或逐张'],
        ['主精翻倍', '该张 ×2', '该张 ×2'],
      ],
    }),
    h.h3('红精招/扎查表（主精 ×2）'),
    checkTable({
      widths: [COL.LABEL, COL.DETAIL],
      header: ['花_皮_赖', '胡数（主精翻倍）'],
      rows: [
        ['2_2_0', '14（主精 28）'],
        ['3_1_0', '12（主精 24）'],
        ['1_3_0', '10（主精 20）'],
        ['0_4_0', '8（主精 16）'],
        ['2_0_2', '24（主精 48）'],
        ['3_0_1', '22（主精 44）'],
        ['1_0_3', '20（主精 40）'],
        ['2_1_1', '18（主精 36）'],
      ],
    }),
    h.p('确认：□ 是 / □ 否', { indent: { firstLine: 0 }, color: '888888' }),

    h.h2('2.7 chuan/fan（穿牌/泛牌）'),
    h.p('定义：5 张同字符。穿牌 = 扎牌后摸到第 5 张或赖子通配；泛牌 = 招牌后摸/旁家打出第 5 张。查精牌 chuan 表。'),
    checkTable({
      widths: [COL.LABEL, COL.DETAIL],
      header: ['成分', '全红', '含黑'],
      rows: [
        ['无精 base', '8 胡', '4 胡'],
        ['精牌/赖子', '查表或逐张', '查表或逐张'],
        ['主精翻倍', '该张 ×2', '该张 ×2'],
      ],
    }),
    h.h3('红精穿/泛查表（主精 ×2）'),
    checkTable({
      widths: [COL.LABEL, COL.DETAIL],
      header: ['花_皮_赖', '胡数（主精翻倍）'],
      rows: [
        ['5_0_0', '28（主精 56）'],
        ['4_1_0', '24（主精 48）'],
        ['3_2_0', '20（主精 40）'],
        ['2_3_0', '16（主精 32）'],
        ['1_4_0', '12（主精 24）'],
        ['3_0_2', '36（主精 72）'],
        ['2_1_2', '48（主精 96）'],
        ['2_0_3', '48（主精 96）'],
        ['0_0_5', '48（主精 96）'],
      ],
    }),
    h.p('确认：□ 是 / □ 否', { indent: { firstLine: 0 }, color: '888888' }),
  ];
}

// ─── 三、主精规则 ───
function section3() {
  return [
    h.h1('三、主精规则'),
    checkTable({
      widths: [COL.LABEL, COL.DETAIL],
      header: ['规则', '说明'],
      rows: [
        ['主精选择', '玩家根据手中牌型自行确定，选择使总胡数最大的方案'],
        ['翻倍方式', '仅翻倍主精字符所在那张牌的计胡值，非整组总和翻倍'],
        ['不可为主精', '乙、九（黑精不可为主精）'],
      ],
    }),
    h.p('确认：□ 是 / □ 否', { indent: { firstLine: 0 }, color: '888888' }),
  ];
}

// ─── 四、赖子规则 ───
function section4() {
  return [
    h.h1('四、赖子规则'),
    checkTable({
      widths: [COL.LABEL, COL.DETAIL],
      header: ['规则', '说明'],
      rows: [
        ['通配范围', '仅可替代三五七（红精），不可替代乙九（黑精），不可替代赖子本身'],
        ['通配计胡', '替代精牌时最少当花精计 +2 胡；若替代字是本场主精，则 +4 胡'],
        ['赖子对子（主精）', '计 8 胡'],
      ],
    }),
    h.p('确认：□ 是 / □ 否', { indent: { firstLine: 0 }, color: '888888' }),
  ];
}

// ─── 五、胡牌条件 ───
function section5() {
  return [
    h.h1('五、胡牌条件'),
    checkTable({
      widths: [COL.LABEL, COL.DETAIL],
      header: ['条件', '说明'],
      rows: [
        ['两听', '7 组型牌（含碰/招/扎/穿/泛）+ 2 眼（对子或口眼）'],
        ['摞听', '8 组型牌（含碰/招/扎/穿/泛）+ 2 眼'],
        ['最低胡数', '≥ 17 胡方可胡牌'],
      ],
    }),
    h.p('确认：□ 是 / □ 否', { indent: { firstLine: 0 }, color: '888888' }),
  ];
}

// ─── 六、胡数→得分换算 ───
function section6() {
  return [
    h.h1('六、胡数→得分换算'),
    checkTable({
      widths: [COL.LABEL, COL.DETAIL],
      header: ['档位', '胡数范围', '基础分', '说明'],
      rows: [
        ['0', '17~21', '3 分', '—'],
        ['1', '22~26', '4 分', '每多 5 胡升一档'],
        ['2', '27~31', '5 分', '—'],
        ['N', '17+5N ~ 21+5N', '3+N 分', 'tier = floor((胡数-17)/5)'],
      ],
    }),
    h.p('公式：tier = floor((胡数 − 17) / 5)，得分 = 3 + tier'),
    h.p('捉统奖惩：未放统旁家每人 −(2 + tier)，放统旁家 −(3 + tier)，捉统赢家 +(5 + tier×2)'),
    h.p('确认：□ 是 / □ 否', { indent: { firstLine: 0 }, color: '888888' }),
  ];
}

// ─── 组装 ───
h.build({
  sections: [
    { noPageNumber: true, children: coverSection() },
    { ...hf, children: [
      h.h1('目  录', { align: 'center', color: C.text }),
      h.spacer(200),
      h.toc(),
    ]},
    { ...hf, children: [
      ...section1(),
      h.pageBreak(),
      ...section2(),
      h.pageBreak(),
      ...section3(),
      ...section4(),
      ...section5(),
      ...section6(),
    ]},
  ],
});