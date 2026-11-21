@echo off
setlocal
title Clean Architecture - Gorev Yonetim Sistemi Baslatici
cd /d "%~dp0"

where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Docker CLI bulunamadi. Docker Desktop kurulu ve PATH icinde olmali.
    pause
    exit /b 1
)

docker info >nul 2>&1
if %errorlevel% equ 0 goto sunucu_baslat

if not exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
    echo [HATA] Docker Desktop.exe bulunamadi. Lutfen Docker Desktop uygulamasini manuel acin.
    pause
    exit /b 1
)

echo Docker motoru arka planda uyandiriliyor...
start "" /min "C:\Program Files\Docker\Docker\Docker Desktop.exe"

set /a deneme=0
:bekle
if %deneme% geq 60 (
    echo [HATA] Docker Desktop 120 saniye icinde hazir olmadi.
    pause
    exit /b 1
)
set /a deneme+=1
timeout /t 2 /nobreak >nul
docker info >nul 2>&1
if %errorlevel% neq 0 goto bekle

:sunucu_baslat
echo Gorev Yonetim Sistemi sunucusu baslatiliyor...
docker compose up -d --build --force-recreate
if %errorlevel% neq 0 (
    echo.
    echo [HATA] Konteyner baslatilamadi. Port 8001 baska bir proje tarafindan kullaniliyor olabilir.
    echo Once diger projeyi durdurun ve tekrar deneyin.
    pause
    exit /b 1
)

where curl.exe >nul 2>&1
if %errorlevel% neq 0 (
    timeout /t 3 /nobreak >nul
    goto tarayici_ac
)

echo API hazir olana kadar bekleniyor...
set /a api_deneme=0
:api_bekle
if %api_deneme% geq 20 (
    echo [UYARI] API 20 saniyede yanit vermedi, yine de tarayici aciliyor...
    goto tarayici_ac
)
set /a api_deneme+=1
curl.exe -fsS http://localhost:8001/api/v1/sistem >nul 2>&1
if %errorlevel% equ 0 goto tarayici_ac
timeout /t 1 /nobreak >nul
goto api_bekle

:tarayici_ac
echo Tarayici aciliyor: http://localhost:8001
start "" http://localhost:8001
endlocal
exit /b 0
