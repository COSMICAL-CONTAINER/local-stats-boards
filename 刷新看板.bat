@echo off
cd /d "%~dp0"
setlocal
if not exist boards mkdir boards

echo [1/2] 正在生成 cc-switch 用量看板 ...
python sources\ccswitch.py > "boards\cc-switch.html"
if errorlevel 1 (
    echo [失败] cc-switch 看板构建出错
    pause
    exit /b 1
)

echo [2/2] 正在生成 WakaTime 编程时长看板 ...
python sources\wakatime.py > "boards\wakatime.html"
if errorlevel 1 (
    echo [失败] WakaTime 看板构建出错（检查网络或 ~/.wakatime.cfg）
    pause
    exit /b 1
)

echo 全部完成！打开 cc-switch 看板 ...
start "" "boards\cc-switch.html"
pause
