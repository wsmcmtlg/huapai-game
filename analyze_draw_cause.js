// ═══════════════════════════════════════════════════════════
// analyze_draw_cause.js — 荒庄成因拆解（只读诊断，不改游戏逻辑）
//
// 复用 measure_winrate.js 的提取/装载/对局驱动（单一真身），
// 通过 opts.onRest 钩子在每个"静息态"采样庄家听牌状态，回答三个问题：
//   A. 听不了？  —— 全程未进听（再分：连结构听都没有 / 有结构听但进不了听）
//   B. 听得太晚？—— 首次进听时牌墙还剩几张（庄家理论上还能摸几次）
//   C. 摸不到？  —— 终局听几张、听口对应的摸牌机会还剩多少
//
// 用法：
//   node analyze_draw_cause.js --level 3 --games 200 [--seed 20261027]
// 输出：measure_report_drawcause_L<level>_<games>.md
// ═══════════════════════════════════════════════════════════
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { loadGameCode, runOneGame, wilsonCI } = require('./measure_winrate.js');

// ── 沙箱内诊断助手（首次调用时注入） ──
// 与页面 _aiCalcTingInfo 同口径：对 22 个字各补一张后用 analyzeHandLoose 判胡。
const DIAG_HELPER = `
;(function(){
  if (typeof __diagPreMelds === 'function') return;
  __diagPreMelds = function() {
    return (G.dealerMelds || []).map(function(m){
      if (m.inHand) {
        var cs = m.cards || [];
        return { type: 'zha', chars: cs.map(function(c){ return c.ch; }), cards: cs.slice(0, 4) };
      }
      var cs2 = m.cards || [];
      return { type: m.type || 'pen', chars: Array(m.count).fill(m.char), cards: cs2 };
    });
  };
  // 听牌评估（三级判定，两个口径同时打）：
  //   canWin  = analyzeHand 进胡（≥17 胡门槛，真能胡）
  //   canForm = analyzeHandLoose 能成牌（成形+眼，但不看胡数门槛）
  //   maxHu   = loose 口径下的最高胡数（判断"差多少胡"）
  __diagTingInfo = function(hand, pm) {
    var canWin = false, winChars = [], maxWinHu = 0;
    var canForm = false, formChars = [], maxFormHu = 0;
    for (var i = 0; i < ALL_22_CHARS.length; i++) {
      var t = ALL_22_CHARS[i];
      var test = hand.slice(); test.push(makeCardData(t));
      var rs = analyzeHand(test, pm);
      if (rs && rs.isWin) { canWin = true; winChars.push(t); if (rs.totalHu > maxWinHu) maxWinHu = rs.totalHu; }
      var rl = analyzeHandLoose(test, pm);
      if (rl && rl.isWin) { canForm = true; formChars.push(t); if (rl.totalHu > maxFormHu) maxFormHu = rl.totalHu; }
      else if (rl && rl.melds && rl.melds.length && rl.totalHu > maxFormHu) maxFormHu = rl.totalHu; // 未成形但有拆解分，用作"胡数差点"
    }
    return { canWin: canWin, winChars: winChars, maxWinHu: maxWinHu,
             canForm: canForm, formChars: formChars, maxFormHu: maxFormHu,
             canTing: canWin, tingCount: winChars.length, tingChars: winChars,
             canTingStruct: canForm };
  };
  // 牌墙中某字剩余张数（= 庄家还能摸到几张）
  __diagWallCount = function(ch) {
    var n = 0;
    for (var i = 0; i < G.deck.length; i++) {
      var s = G.deck[i]; var c = s.indexOf(':') >= 0 ? s.substring(0, s.indexOf(':')) : s;
      if (c === ch) n++;
    }
    return n;
  };
  // 对手手中某字张数（= 被截张数）
  __diagOppCount = function(ch) {
    var n = 0;
    for (var p = 1; p <= 2; p++) {
      var h = opponentHands[p] || [];
      for (var i = 0; i < h.length; i++) if (h[i] === ch) n++;
    }
    return n;
  };
  __diagSnapshot = function(tag) {
    var pm = __diagPreMelds();
    var hand = handCards.slice();
    var sn = {
      tag: tag,
      handLen: hand.length,
      deckCount: G.deckCount,
      meldCount: (G.dealerMelds || []).length,
      meldTypes: (G.dealerMelds || []).map(function(m){ return m.type; }),
      round: G.round || 0,
    };
    // 起手 26 张是否为天胡（不加牌直接判胡）
    if (tag === 'deal') {
      var dh = analyzeHand(hand.slice(), []);
      sn.dealHu = !!(dh && dh.isWin);
      sn.dealHuCnt = dh && dh.isWin ? (dh.totalHu || 0) : 0;
      return sn;
    }
    var t = __diagTingInfo(hand, pm);
    sn.canWin = t.canWin; sn.winChars = t.winChars; sn.maxWinHu = t.maxWinHu;
    sn.canForm = t.canForm; sn.formChars = t.formChars; sn.maxFormHu = t.maxFormHu;
    sn.canTing = t.canWin; sn.tingCount = t.winChars.length; sn.tingChars = t.winChars;
    sn.canTingStruct = t.canForm; sn.maxHu = t.maxFormHu;
    var wall = 0, opp = 0;
    for (var i = 0; i < t.winChars.length; i++) {
      wall += __diagWallCount(t.winChars[i]);
      opp += __diagOppCount(t.winChars[i]);
    }
    sn.tingWallLeft = wall;   // 听口在牌墙中的总张数
    sn.tingOppHold = opp;     // 听口被对手持有的张数（被截）
    return sn;
  };
})();
`;

function analyze(level, games, seed) {
  const loader = loadGameCode();
  const levelNames = ['菜鸟', '高手', '大师', '老千'];
  const rows = [];
  let errs = 0;

  for (let g = 0; g < games; g++) {
    process.stdout.write(`\r拆解中 ${g + 1}/${games}`);
    const samples = [];
    let inited = false;
    const onRest = (vmctx, tag) => {
      if (!inited) { vm.runInContext(DIAG_HELPER, vmctx); inited = true; }
      samples.push(vm.runInContext(`__diagSnapshot(${JSON.stringify(tag)})`, vmctx));
    };
    let r;
    try {
      r = runOneGame(loader, [level, 1, 1], seed + g * 7919, { onRest });
    } catch (e) {
      errs++; rows.push({ g, error: e.message }); continue;
    }
    const turns = samples.filter(s => s.tag === 'turn' || s.tag === 'claim');
    const final = samples.filter(s => s.tag === 'final')[0] || samples[samples.length - 1];
    const deal = samples.filter(s => s.tag === 'deal')[0];
    const winSamples = turns.filter(s => s.canWin === true);      // 真听（≥17 胡）
    const formSamples = turns.filter(s => s.canForm === true);    // 能成形（不看门槛）
    const firstWin = winSamples[0] || null;
    const firstForm = formSamples[0] || null;
    rows.push({
      g, winner: r.winner, hu: r.hu,
      dealtWall: deal ? deal.deckCount : null,   // 起手后牌墙数
      dealHu: deal ? !!deal.dealHu : false,      // 起手 26 张即为胡（天胡）
      turns: turns.length,
      everWin: !!firstWin,
      everForm: !!firstForm,
      firstWinWall: firstWin ? firstWin.deckCount : null,
      firstWinTingCount: firstWin ? firstWin.tingCount : 0,
      firstWinWallLeft: firstWin ? firstWin.tingWallLeft : 0,
      firstWinOppHold: firstWin ? firstWin.tingOppHold : 0,
      firstFormWall: firstForm ? firstForm.deckCount : null,
      maxFormHu: Math.max(...turns.map(s => s.maxFormHu || 0), 0),
      finalDeck: final ? final.deckCount : 0,
      finalTingCount: final && final.tingCount ? final.tingCount : 0,
      finalMaxFormHu: final ? (final.maxFormHu || 0) : 0,
      finalCanWin: final ? !!final.canWin : false,
      finalHandLen: final ? final.handLen : 0,
      finalMelds: final ? final.meldCount : 0,
      melds: final ? final.meldTypes : [],
      winTurns: winSamples.length,
      formTurns: formSamples.length,
      win: r.winner >= 0,
    });
  }
  process.stdout.write('\n');
  return { rows, loader, errs };
}

// ── 汇总 ──
function bucketWall(n) {
  if (n === null || n === undefined) return 'n/a';
  if (n <= 3) return '0~3 (≤1次摸牌)';
  if (n <= 6) return '4~6 (≤2次)';
  if (n <= 12) return '7~12 (≤4次)';
  if (n <= 18) return '13~18 (≤6次)';
  return '19+ (7次以上)';
}

function main() {
  const args = process.argv.slice(2);
  const getArg = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
  const level = +getArg('--level', 3);
  const games = +getArg('--games', 200);
  const seed = +getArg('--seed', 20261027);
  const levelNames = ['菜鸟', '高手', '大师', '老千'];

  console.log(`荒庄成因拆解：${levelNames[level]}(庄) vs 2×高手陪练，${games} 局`);
  const t0 = Date.now();
  const { rows, errs } = analyze(level, games, seed);
  const secs = (Date.now() - t0) / 1000;
  console.log(`耗时 ${secs.toFixed(0)}s（${(secs / games).toFixed(2)}s/局），异常 ${errs} 局`);

  const draws = rows.filter(r => !r.error && r.winner === -1);
  const dealerWins = rows.filter(r => !r.error && r.winner === 0);   // 庄家自己胡的局（对照口径）
  const oppWins = rows.filter(r => !r.error && r.winner > 0);        // 旁家胡的局（不参与庄家对照）
  const wins = dealerWins; // 兼容下方引用：对照只用庄家胡的局
  const n = rows.length;
  const pct = (a, b) => b ? (a / b * 100).toFixed(1) + '%' : 'n/a';
  const avg = (arr) => arr.length ? (arr.reduce((x, y) => x + y, 0) / arr.length) : null;
  const L = [];
  L.push(`# 荒庄成因拆解：${levelNames[level]}（位0庄） vs 2×高手陪练`);
  L.push('');
  L.push(`- 局数：${games}（异常 ${errs}），seed ${seed}，耗时 ${secs.toFixed(0)}s`);
  L.push(`- 荒庄 ${draws.length} 局（${pct(draws.length, n)}）｜庄家胡 ${dealerWins.length} 局｜旁家胡 ${oppWins.length} 局`);

  // 起手牌墙
  const dealWalls = rows.filter(r => r.dealtWall != null).map(r => r.dealtWall);
  L.push(`- 起手发牌后牌墙：${avg(dealWalls)?.toFixed(1)} 张（三家共摸，庄家每 3 张摸 1 张）`);
  L.push(`- 庄家平均出牌回合数：${avg(draws.map(r => r.turns))?.toFixed(1)}（荒庄局）／${avg(wins.map(r => r.turns))?.toFixed(1)}（胡牌局）`);
  L.push(`- 起手 26 张即为胡（天胡）的：${rows.filter(r => r.dealHu).length} 局（${pct(rows.filter(r => r.dealHu).length, n)}）`);
  L.push('');

  // ── A/B/C 分类（互斥，按"最远走到哪一步"分） ──
  // A1 从未成形（loose 口径也不成形）
  // A2 成形过但从未进胡（胡数始终不够 17）
  // B  进过胡（真听）但牌墙耗尽
  const A1 = draws.filter(r => !r.everForm);
  const A2 = draws.filter(r => r.everForm && !r.everWin);
  const B = draws.filter(r => r.everWin);
  L.push('## 一、荒庄归因（互斥三类，按"最远走到哪一步"分）');
  L.push('');
  L.push('| 类别 | 含义 | 局数 | 占荒庄 |');
  L.push('|---|---|---|---|');
  L.push(`| A1 | 全程未成形（牌型从头到尾拆不出来） | ${A1.length} | ${pct(A1.length, draws.length)} |`);
  L.push(`| A2 | 成形过但从未进胡（胡数始终不够 17） | ${A2.length} | ${pct(A2.length, draws.length)} |`);
  L.push(`| B | 进过胡（真听过）但牌墙耗尽未胡 | ${B.length} | ${pct(B.length, draws.length)} |`);
  L.push('');
  if (A2.length) {
    const near = A2.filter(r => r.maxFormHu >= 14).length;
    L.push(`- A2 里"差一点点"（成形时最高胡数 ≥14，离 17 门槛 ≤3 胡）的：${near} 局（${pct(near, A2.length)}）`);
    L.push(`- A2 成形时最高胡数：平均 ${avg(A2.map(r => r.maxFormHu))?.toFixed(1)} 胡`);
  }
  if (A1.length) {
    L.push(`- A1 成形时最高胡数：平均 ${avg(A1.map(r => r.maxFormHu))?.toFixed(1)} 胡`);
  }
  L.push('');

  // ── 首次进胡时机 ──
  L.push('## 二、首次进胡（真听）时机 —— 荒庄 vs 胡牌对照');
  L.push('');
  L.push('牌墙剩余 = 首次能胡那一刻墙上还有几张（三家轮流摸，庄家理论还能摸 ≈⌈剩余/3⌉ 次）。');
  L.push('');
  const buckets = ['0~3 (≤1次摸牌)', '4~6 (≤2次)', '7~12 (≤4次)', '13~18 (≤6次)', '19+ (7次以上)'];
  const winListeners = wins.filter(r => r.everWin);
  L.push('| 首次进胡时牌墙剩余 | B 类荒庄 | 胡牌局 |');
  L.push('|---|---|---|');
  for (const b of buckets) {
    const db = B.filter(r => bucketWall(r.firstWinWall) === b).length;
    const wb = winListeners.filter(r => bucketWall(r.firstWinWall) === b).length;
    L.push(`| ${b} | ${db}（${pct(db, B.length)}） | ${wb}（${pct(wb, winListeners.length)}） |`);
  }
  L.push('');
  const bAvg = avg(B.map(r => r.firstWinWall));
  const wAvg = avg(winListeners.map(r => r.firstWinWall));
  L.push(`- B 类荒庄：首次进胡时牌墙剩余 **${bAvg?.toFixed(1)}** 张（≈还能摸 ${(bAvg / 3).toFixed(1)} 次）`);
  L.push(`- 胡牌局：首次进胡时牌墙剩余 **${wAvg?.toFixed(1)}** 张（≈还能摸 ${(wAvg / 3).toFixed(1)} 次）`);
  L.push(`- 胡牌局中"首次进胡时牌墙已 ≤6 张"的：${winListeners.filter(r => r.firstWinWall <= 6).length} 局（靠运气收的）`);
  L.push(`- 胡牌局中从未采样到听牌（一手胡/捉铳直接收的）：${wins.filter(r => !r.everWin).length} 局`);
  L.push('');
  L.push(`- B 类首次进胡时的听口数：平均 ${avg(B.map(r => r.firstWinTingCount))?.toFixed(1)} 个`);
  L.push(`- B 类首次进胡时听口在墙中的张数：平均 ${avg(B.map(r => r.firstWinWallLeft))?.toFixed(1)} 张；被对手持有的：平均 ${avg(B.map(r => r.firstWinOppHold))?.toFixed(1)} 张`);
  L.push(`- B 类进胡后仍能保持听牌的静息回合数：平均 ${avg(B.map(r => r.winTurns))?.toFixed(1)} 个`);
  L.push('');

  // ── 成形时机（A2 视角） ──
  L.push('## 三、成形（能拆出牌型）的时机');
  L.push('');
  L.push(`- 荒庄局首次成形时牌墙剩余：平均 ${avg(draws.filter(r => r.everForm).map(r => r.firstFormWall))?.toFixed(1)} 张`);
  L.push(`- 胡牌局首次成形时牌墙剩余：平均 ${avg(wins.filter(r => r.everForm).map(r => r.firstFormWall))?.toFixed(1)} 张`);
  L.push(`- 荒庄局从头到尾没成形的：${A1.length} 局（${pct(A1.length, draws.length)}）`);
  L.push('');

  // ── 终局形态 ──
  L.push('## 四、荒庄终局牌型（庄家）');
  L.push('');
  L.push(`- 终局仍在听（能胡）的：${draws.filter(r => r.finalCanWin).length} 局（${pct(draws.filter(r => r.finalCanWin).length, draws.length)}）`);
  L.push(`- 终局听口数：平均 ${avg(draws.filter(r => r.finalTingCount > 0).map(r => r.finalTingCount))?.toFixed(1)} 个`);
  L.push(`- 终局成形（能拆牌型）的：${draws.filter(r => r.finalMaxFormHu > 0).length} 局（${pct(draws.filter(r => r.finalMaxFormHu > 0).length, draws.length)}）`);
  const meldStat = {};
  for (const r of draws) { const k = (r.melds || []).length; meldStat[k] = (meldStat[k] || 0) + 1; }
  L.push(`- 荒庄局庄家明牌组数分布：${Object.keys(meldStat).sort().map(k => `${k}组:${meldStat[k]}`).join(' / ')}`);
  const winMeldStat = {};
  for (const r of wins) { const k = (r.melds || []).length; winMeldStat[k] = (winMeldStat[k] || 0) + 1; }
  L.push(`- 胡牌局庄家明牌组数分布：${Object.keys(winMeldStat).sort().map(k => `${k}组:${winMeldStat[k]}`).join(' / ')}`);
  L.push('');

  // ── 结论提示 ──
  L.push('## 五、读数提示');
  L.push('');
  const shareB = B.length / (draws.length || 1);
  const shareA2 = A2.length / (draws.length || 1);
  const shareA1 = A1.length / (draws.length || 1);
  if (shareB >= 0.4) {
    L.push(`- **B 类（进过胡但摸空）占 ${pct(B.length, draws.length)}**，首次进胡时牌墙平均只剩 ${bAvg?.toFixed(1)} 张（对照胡牌局 ${wAvg?.toFixed(1)} 张）：荒庄的第一位原因是**进听太晚**，牌墙只剩 1~2 次摸牌机会。`);
  }
  if (shareA2 >= 0.25) {
    L.push(`- **A2 类（成形但胡数不够）占 ${pct(A2.length, draws.length)}**：牌已经拆得出，卡在 17 胡门槛——旋钮是"凑胡数"（精牌/花皮/赖子去向），不是碰吃门槛。`);
  }
  if (shareA1 >= 0.4) {
    L.push(`- **A1 类（全程未成形）占 ${pct(A1.length, draws.length)}**：牌型根本不通，对应"放宽碰/招/吃与结构搭建"的方向。`);
  }
  const report = L.join('\n');
  console.log('\n' + report);
  const base = `measure_report_drawcause_L${level}_${games}`;
  fs.writeFileSync(path.join(__dirname, base + '.md'), report);
  fs.writeFileSync(path.join(__dirname, base + '.json'), JSON.stringify(rows, null, 1));
  console.log(`已写入 ${base}.md / ${base}.json`);
}

main();
