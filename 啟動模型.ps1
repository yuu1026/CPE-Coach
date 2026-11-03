param([switch]$BaseModel)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
. (Join-Path $PSScriptRoot '啟動共用.ps1')
Assert-CpePortAvailable -Port 11436
$python = Get-CpePython
if ($BaseModel) {
    $selection = [pscustomobject]@{name='gemma-3-4b-it'; adapter_path=''}
} else {
    $selectionJson = & $python -c "import json; from model_backend import active_deployment; print(json.dumps(active_deployment()))"
    if ($LASTEXITCODE -ne 0) { throw '無法驗證目前模型部署設定。' }
    $selection = $selectionJson | ConvertFrom-Json
}
if (-not $env:HF_MODEL_PATH) { $env:HF_MODEL_PATH = Join-Path $PSScriptRoot 'models/gemma-3-4b-it' }
$env:HF_USE_BASE_MODEL = if ($BaseModel -or -not $selection.adapter_path) { '1' } else { '0' }
$env:HF_SERVE_MODEL_NAME = $selection.name
$env:HF_ADAPTER_PATH = $selection.adapter_path
& $python local_model_server.py
