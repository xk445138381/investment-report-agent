# 一键启动投资报告 Agent
# 用法: powershell -ExecutionPolicy Bypass -File start.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "=== 投资报告 Agent 启动 ===" -ForegroundColor Cyan
Write-Host "项目路径: $root" -ForegroundColor Gray

# 1. 加载环境变量
$envFile = Join-Path $root "backend\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#].+?)=(.+)\s*$') {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2].Trim(), "Process")
        }
    }
    Write-Host "[OK] 环境变量已加载" -ForegroundColor Green
} else {
    Write-Host "[WARN] 未找到 backend\.env 文件" -ForegroundColor Yellow
}

# 2. 启动后端
Write-Host "[..] 启动后端 (端口 8000)..." -ForegroundColor Gray
$backendDir = Join-Path $root "backend"
Start-Process python -ArgumentList "-m","uvicorn","src.api.main:app","--host","0.0.0.0","--port","8000","--log-level","warning" -WorkingDirectory $backendDir -NoNewWindow
Start-Sleep 3

# 3. 启动前端
Write-Host "[..] 启动前端 (端口 3000)..." -ForegroundColor Gray
$frontendDir = Join-Path $root "frontend"
Start-Process npm -ArgumentList "run","dev" -WorkingDirectory $frontendDir -NoNewWindow
Start-Sleep 5

# 4. 验证
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
    Write-Host "[OK] 后端运行中: $($health.status) v$($health.version)" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] 后端未响应" -ForegroundColor Red
}

try {
    $fe = Invoke-WebRequest -Uri "http://localhost:3000" -TimeoutSec 10 -UseBasicParsing
    Write-Host "[OK] 前端运行中: HTTP $($fe.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "[..] 前端启动中（首次编译需要约30秒）..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== 访问地址 ===" -ForegroundColor Cyan
Write-Host "  首页:    http://localhost:3000"
Write-Host "  价值投资: http://localhost:3000/progress?ticker=600519.SH&depth=value&template=value_investor"
Write-Host "  API:     http://localhost:8000/docs"
Write-Host "  调试:    http://localhost:8000/api/v1/debug/env"
Write-Host ""
Write-Host "按 Ctrl+C 停止所有服务" -ForegroundColor Gray
