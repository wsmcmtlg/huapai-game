const path = require('path');
const fs = require('fs');

const h = require(path.join(process.env.SKILL_PATH, 'docx', 'scripts', 'docx-helper'))({
  fonts: { heading: 'SimHei', body: 'Microsoft YaHei' },
  sizes: { h1: 36, h2: 30, h3: 26, body: 20 },
  colors: { primary: '1B4F72', text: '2C3E50', border: 'AEB6BF', light: 'EBF5FB', accent: '2E86C1' },
  page: { width: 11906, height: 16838, margins: { top: 1200, bottom: 1000, left: 1100, right: 1100 } },
  indent: 0,
});

const C = h.colors;

// ── 读取回放数据 ──
const dataPath = path.join('C:\\Users\\XBW\\Documents\\lingxi-claw\\20260509-19-35-44-847', 'replay_data.json');
const replayData = JSON.parse(fs.readFileSync(dataPath, 'utf-8'));

// ── 解析回放文本 ──
function parseReplay(text) {
  const lines = text.split('\n');
  const info = { winner: '', huHu: 0, huType: '', score: 0, steps: 0, mainJin: '', viceJin: '' };

  for (const line of lines) {
    const huMatch = line.match(/\[\s*胡\s*牌\s*\]\s*(\S+)\s+(\d+)胡\s+(\S+)\s+得(\d+)分/);
    if (huMatch) {
      info.winner = huMatch[1];
      info.huHu = parseInt(huMatch[2]);
      info.huType = huMatch[3];
      info.score = parseInt(huMatch[4]);
    }
    const detailMatch = line.match(/主精=(\S+)\s*\|\s*副精=(\S+)/);
    if (detailMatch) {
      info.mainJin = detailMatch[1];
      info.viceJin = detailMatch[2] === '无' ? '无' : detailMatch[2];
    }
    const stepMatch = line.match(/\u603b\u6b65\u9aa4:\s*(\d+)/);
    if (stepMatch) info.steps = parseInt(stepMatch[1]);
  }
  return info;
}

const parsed = replayData.map(r => parseReplay(r.text));

// ── 封面 ──
function coverSection() {
  return [
    h.spacer(3000),
    h.p('湖北花牌', { size: 56, bold: true, color: C.primary, align: 'center' }),
    h.spacer(200),
    h.p('胡牌对局文字回放', { size: 36, color: C.accent, align: 'center' }),
    h.spacer(600),
    h.divider(C.primary, 6),
    h.spacer(400),
    h.p('智能AI引擎  /  规则引擎v1', { size: 22, color: '7F8C8D', align: 'center' }),
    h.spacer(200),
    h.p('5局胡牌牌局完整记录', { size: 22, color: '7F8C8D', align: 'center' }),
    h.spacer(2000),
    h.p('2026年5月14日', { size: 20, color: '95A5A6', align: 'center' }),
  ];
}

// ── 目录 ──
function tocSection() {
  return [
    h.h1('目  录', { align: 'center' }),
    h.spacer(200),
    h.toc(),
  ];
}

// ── 汇总页 ──
function summarySection() {
  const avgHu = (parsed.reduce((s, p) => s + p.huHu, 0) / parsed.length).toFixed(1);
  const avgStep = (parsed.reduce((s, p) => s + p.steps, 0) / parsed.length).toFixed(0);

  return [
    h.h1('对局汇总', { bookmark: '_summary' }),
    h.spacer(200),
    h.table({
      widths: [800, 1800, 1400, 1400, 1200, 1200, 1800],
      header: ['序号', '胡牌玩家', '胡数', '胡牌方式', '得分', '主精', '总步骤'],
      headerColor: C.primary,
      rows: parsed.map((p, i) => [
        `${i + 1}`,
        p.winner,
        `${p.huHu}胡`,
        p.huType,
        `${p.score}分`,
        p.mainJin,
        `${p.steps}步`,
      ]),
      altColor: C.light,
      cellSize: 20,
    }),
    h.spacer(400),
    h.p([
      h.text(`共 ${parsed.length} 局胡牌对局。平均 ${avgHu} 胡，平均 ${avgStep} 步完成。所有对局均为捉统胡牌方式。`, { color: '5D6D7E' }),
    ]),
  ];
}

// ── 回放行样式 ──
function styleReplayLine(trimmed) {
  let lineColor = '2C3E50';
  let bold = false;

  if (trimmed.includes('湖北花牌') || (trimmed.includes('=') && trimmed.replace(/=/g, '').trim() === '')) {
    lineColor = C.primary; bold = true;
  } else if (trimmed.includes('胡 牌')) {
    lineColor = 'C0392B'; bold = true;
  } else if (trimmed.includes('流局')) {
    lineColor = '7F8C8D';
  } else if (trimmed.includes('>>>') || trimmed.includes('扎牌')) {
    lineColor = '8E44AD';
  } else if (trimmed.includes('!!') || trimmed.includes('捉统') || trimmed.includes('自摸') || trimmed.includes('天胡')) {
    lineColor = 'E74C3C'; bold = true;
  } else if (trimmed.includes('===') || trimmed.includes('结算')) {
    lineColor = 'D35400'; bold = true;
  } else if (trimmed.includes('牌型拆分') || trimmed.includes('计胡明细')) {
    lineColor = '1A5276'; bold = true;
  } else if (trimmed.includes('合计')) {
    lineColor = '1A5276'; bold = true;
  } else if (trimmed.includes('>>') || trimmed.includes('出牌')) {
    lineColor = '2E86C1';
  } else if (trimmed.includes('::') || trimmed.includes('摸牌')) {
    lineColor = '5D6D7E';
  } else if (trimmed.includes('<') || trimmed.includes('对牌') || trimmed.includes('招牌') || trimmed.includes('吃牌')) {
    lineColor = '27AE60';
  }

  return { lineColor, bold };
}

// ── 单局详情 ──
function roundSection(roundIdx) {
  const info = parsed[roundIdx];
  const rawLines = replayData[roundIdx].text.split('\n');
  const children = [];

  children.push(
    h.h1(`第 ${roundIdx + 1} 局  ${info.winner}  ${info.huHu}胡`, { bookmark: `_round${roundIdx + 1}` })
  );

  // 基本信息表格
  children.push(h.spacer(100));
  children.push(h.table({
    widths: [2000, 3000, 2000, 3000],
    header: ['胡牌玩家', '', '胡牌方式', ''],
    headerColor: C.primary,
    rows: [
      [info.winner, '', info.huType, ''],
      ['总胡数', `${info.huHu}胡`, '得分', `${info.score}分`],
      ['主精', info.mainJin, '副精', info.viceJin],
      ['总步骤', `${info.steps}步`, '搜索次数', `第${replayData[roundIdx].search_n}次`],
    ],
    altColor: C.light,
    cellSize: 20,
  }));

  // 完整回放
  children.push(h.spacer(300));
  children.push(h.h2('完整回放记录'));
  children.push(h.spacer(100));

  for (const line of rawLines) {
    const trimmed = line.trimEnd();
    if (trimmed === '') {
      children.push(h.p('', { spacing: { before: 40, after: 40 } }));
      continue;
    }

    const { lineColor, bold } = styleReplayLine(trimmed);

    children.push(h.p(trimmed, {
      font: 'Consolas',
      size: 16,
      color: lineColor,
      bold: bold,
      spacing: { before: 0, after: 0, line: 240, lineRule: 'auto' },
      indent: { left: 100 },
    }));
  }

  return children;
}

// ── 组装 ──
const hf = h.headerFooter('湖北花牌 - 胡牌对局回放记录');

const allRoundChildren = [];
for (let i = 0; i < parsed.length; i++) {
  allRoundChildren.push(...roundSection(i));
}

h.build({
  sections: [
    { children: coverSection() },
    { ...hf, children: tocSection() },
    { ...hf, children: [...summarySection()] },
    { ...hf, children: [...allRoundChildren] },
  ],
}, [
  { type: 'coverColor', colors: ['0E3D5B', '1B4F72', '1A5276'], direction: 'vertical' },
]);
