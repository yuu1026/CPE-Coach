param(
    [ValidateSet('Model','Website')][string]$Service = 'Model',
    [ValidatePattern('^gemma3-quality-v[0-9]+$')][string]$RunName = 'gemma3-quality-v5'
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
. (Join-Path $PSScriptRoot '啟動共用.ps1')
$adapter = Join-Path $PSScriptRoot "training/runs/$RunName"
$reportPath = Join-Path $adapter 'training_report.json'
if (-not (Test-Path -LiteralPath $reportPath)) { throw '找不到完整訓練報告；不會載入中斷或只有檢查點的實驗。' }
$report = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($report.smoke_only -ne $false -or $report.optimizer_steps -le 0 -or $report.optimizer_steps -ne $report.expected_steps) {
    throw '訓練未完整完成，不能使用此啟動入口。'
}
if (-not (Test-Path -LiteralPath (Join-Path $adapter 'adapter_model.safetensors'))) { throw '找不到本地 Adapter 權重；GitHub 不包含模型權重。' }
$modelName = 'gemma-3-4b-' + $RunName.Substring(7)
Write-Host "品質實驗：$modelName。這不是一般啟動入口的預設模型，請參考實際評估報告。"
if ($Service -eq 'Model') {
    Assert-CpePortAvailable -Port 11436
    $python = Get-CpePython -Purpose Model
    $env:HF_USE_BASE_MODEL = '0'
    $env:HF_ADAPTER_PATH = $adapter
    $env:HF_SERVE_MODEL_NAME = $modelName
    if (-not $env:HF_MODEL_PATH) { $env:HF_MODEL_PATH = Join-Path $PSScriptRoot 'models/gemma-3-4b-it' }
    & $python local_model_server.py
} else {
    Assert-CpePortAvailable -Port 8000
    $python = Get-CpePython -Purpose Website
    $env:HINT_MODE = 'live'
    $env:Model_URL = 'http://127.0.0.1:11436'
    $env:Model_Name = $modelName
    $env:CONTEXT_TOKENS = '4096'
    & $python manage.py runserver 127.0.0.1:8000
}
