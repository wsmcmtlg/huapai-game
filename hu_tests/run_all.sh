#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
# 公安花牌 - 计胡/拆牌 一键回归测试
# 用法: bash hu_tests/run_all.sh  （在游戏目录下执行，或直接执行本脚本）
# 说明: 每次修改 step5-hu.html 中涉及计胡/拆牌/精牌查表的逻辑后，务必运行本脚本，
#       确保历史修复不回归、精牌查表完整、性能在预算内。
# ═══════════════════════════════════════════════════════
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."   # 切到游戏目录（step5-hu.html 所在）

echo "════════ 1/6 提取核心代码 ════════"
python hu_tests/extract_core.py step5-hu.html hu_tests/hu_core_current.js step5-hu_backup_before_flowskin_swap.html hu_tests/hu_core_before.js || { echo "[提取失败]"; exit 1; }
echo ""

PASS=0
FAIL=0
run() {
  echo "════════ 运行 $1 ════════"
  if node "$1"; then
    PASS=$((PASS+1))
    echo "[通过] $1"
  else
    FAIL=$((FAIL+1))
    echo "[失败] $1"
  fi
  echo ""
}

run test_hu_tables_complete.js   # 精牌查表全量(39项)+完整性
run test_hu_flowskin_swap.js     # 修复1: 穿牌花皮重分配(70→84)
run test_hu_chuan_032.js         # 修复2: 穿牌3皮2赖查表(41→67)
run test_hu_regression.js        # 回归5用例(不劣化/不误改/扎牌/无扩展)
run test_chuan_table.js          # 红精穿牌6条表驱动
run test_hu_perf.js              # 性能(120ms AI预算内)
run test_ai_risk.js              # Phase7: AI期望损失(两害相权取其轻)

echo "════════════════════════════════════════"
echo "结果: 通过 $PASS / 失败 $FAIL"
if [ "$FAIL" -eq 0 ]; then
  echo "✅ 全部通过"
else
  echo "❌ 存在失败，请检查上述 [失败] 项"
fi
exit "$FAIL"
