@echo off
cd /d "%~dp0"
setlocal

echo [1/2] 正在从 cc-switch 数据库聚合最新数据并重建看板 ...
python build.py > "cc-switch-统计看板.html"
if errorlevel 1 (
    echo.
    echo [失败] 构建出错，请确认已安装 Python 3 且本目录包含 build.py / template.html / echarts.min.js
    pause
    exit /b 1
)

echo [2/2] 完成！最新看板已生成并将在浏览器中打开：
echo        %cd%\cc-switch-统计看板.html
echo.
start "" "cc-switch-统计看板.html"
pause
