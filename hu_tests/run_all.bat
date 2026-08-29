@echo off
chcp 65001 >nul
REM ═══════════════════════════════════════════════════════
REM 公安花牌 - 计胡/拆牌 一键回归测试（Windows 双击运行）
REM 修改 step5-hu.html 中计胡/拆牌/精牌查表逻辑后，务必双击本脚本验证不回归
REM ═══════════════════════════════════════════════════════
cd /d "%~dp0.."

echo ════════ 1/6 提取核心代码 ════════
python hu_tests\extract_core.py step5-hu.html hu_tests\hu_core_current.js step5-hu_backup_before_flowskin_swap.html hu_tests\hu_core_before.js
if errorlevel 1 (
  echo [提取失败] 请确认已安装 Python 3
  pause
  exit /b 1
)
echo.

set PASS=0
set FAIL=0

echo ════════ 运行 test_hu_tables_complete.js ════════
node test_hu_tables_complete.js
if errorlevel 1 (set /a FAIL+=1 & echo [失败] test_hu_tables_complete.js) else (set /a PASS+=1 & echo [通过] test_hu_tables_complete.js)
echo.

echo ════════ 运行 test_hu_flowskin_swap.js ════════
node test_hu_flowskin_swap.js
if errorlevel 1 (set /a FAIL+=1 & echo [失败] test_hu_flowskin_swap.js) else (set /a PASS+=1 & echo [通过] test_hu_flowskin_swap.js)
echo.

echo ════════ 运行 test_hu_chuan_032.js ════════
node test_hu_chuan_032.js
if errorlevel 1 (set /a FAIL+=1 & echo [失败] test_hu_chuan_032.js) else (set /a PASS+=1 & echo [通过] test_hu_chuan_032.js)
echo.

echo ════════ 运行 test_hu_regression.js ════════
node test_hu_regression.js
if errorlevel 1 (set /a FAIL+=1 & echo [失败] test_hu_regression.js) else (set /a PASS+=1 & echo [通过] test_hu_regression.js)
echo.

echo ════════ 运行 test_chuan_table.js ════════
node test_chuan_table.js
if errorlevel 1 (set /a FAIL+=1 & echo [失败] test_chuan_table.js) else (set /a PASS+=1 & echo [通过] test_chuan_table.js)
echo.

echo ════════ 运行 test_hu_perf.js ════════
node test_hu_perf.js
if errorlevel 1 (set /a FAIL+=1 & echo [失败] test_hu_perf.js) else (set /a PASS+=1 & echo [通过] test_hu_perf.js)
echo.

echo ════════════════════════════════════════
echo 结果: 通过 %PASS% / 失败 %FAIL%
if %FAIL%==0 (echo ✅ 全部通过) else (echo ❌ 存在失败，请检查上述 [失败] 项)
echo.
pause
