@echo off
REM ==========================================================================
REM run_all.bat — 一键顺序执行 (开发期辅助, 不替代 CMO Lua 控制台)
REM   流程: main.lua -> clear.lua -> reload.lua -> attack.lua
REM   必须在 CMO 已加载场景后, 在游戏脚本目录里跑这个 bat
REM ==========================================================================

setlocal

set SCRIPT_DIR=%~dp0
set CMO_SCRIPTS=%USERPROFILE%\Documents\Command Modern Operations\Scenarios\Scripts

echo ==========================================================================
echo   消耗与诱歼作战方案 - 一键脚本套件
echo   工作目录: %SCRIPT_DIR%
echo ==========================================================================
echo.

echo [STEP 1/4] main.lua ...
if exist "%SCRIPT_DIR%main.lua" (
    copy /Y "%SCRIPT_DIR%main.lua" "%CMO_SCRIPTS%\" >nul
    echo   ^>^> copied to CMO scripts folder
) else (
    echo   [X] main.lua 不存在
    goto END
)

echo [STEP 2/4] clear.lua ...
if exist "%SCRIPT_DIR%clear.lua" (
    copy /Y "%SCRIPT_DIR%clear.lua" "%CMO_SCRIPTS%\" >nul
)

echo [STEP 3/4] reload.lua ...
if exist "%SCRIPT_DIR%reload.lua" (
    copy /Y "%SCRIPT_DIR%reload.lua" "%CMO_SCRIPTS%\" >nul
)

echo [STEP 4/4] attack.lua ...
if exist "%SCRIPT_DIR%attack.lua" (
    copy /Y "%SCRIPT_DIR%attack.lua" "%CMO_SCRIPTS%\" >nul
)

echo.
echo ==========================================================================
echo   全部脚本已复制到: %CMO_SCRIPTS%
echo   下一步: 在 CMO Lua Console 中依次执行:
echo     dofile("main.lua")
echo     dofile("clear.lua")
echo     dofile("reload.lua")
echo     dofile("attack.lua")
echo   然后推进游戏时间以触发事件
echo ==========================================================================

:END
endlocal