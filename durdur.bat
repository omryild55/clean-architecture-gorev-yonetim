@echo off
setlocal
title Clean Architecture - Gorev Yonetim Sistemi Durdurucu
cd /d "%~dp0"

where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Docker CLI bulunamadi. Docker Desktop kurulu ve PATH icinde olmali.
    pause
    exit /b 1
)

echo Gorev Yonetim Sistemi konteyneri durduruluyor...
docker compose down
if %errorlevel% neq 0 (
    echo.
    echo [HATA] Konteyner durdurulamadi. Docker Desktop acik mi kontrol edin.
    pause
    exit /b 1
)

echo Gorev Yonetim Sistemi basariyla durduruldu.
timeout /t 2 /nobreak >nul
endlocal
exit /b 0
