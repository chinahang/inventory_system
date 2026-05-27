@echo off
chcp 65001 >nul
cd /d %~dp0
echo 正在启动台州海昌物流进销存系统...
echo 启动后请用浏览器访问 http://localhost:8000
echo 按 Ctrl+C 停止系统
echo.
python main.py
pause
