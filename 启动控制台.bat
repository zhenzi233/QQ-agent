@echo off
chcp 65001 >nul
title QQ-agent 控制台
cd /d "%~dp0"
echo.
echo   QQ-agent 控制台(headless)
echo   浏览器打开: http://127.0.0.1:3210
echo   关闭此窗口即停止
echo   ----------------------------------------
node src\server.js
pause
