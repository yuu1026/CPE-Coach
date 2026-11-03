param([switch]$BaseModel)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
. (Join-Path $PSScriptRoot '啟動共用.ps1')
$python = Get-CpePython -Purpose Website
if ($BaseModel) {
    $selection = [pscustomobject]@{name='gemma-3-4b-it'; adapter_path=''}
} else {
    $selectionJson = & $python -c "import json; from model_backend import active_deployment; print(json.dumps(active_deployment()))"
    if ($LASTEXITCODE -ne 0) { throw '無法驗證目前模型部署設定。' }
    $selection = $selectionJson | ConvertFrom-Json
}
$env:HINT_MODE = 'live'
$env:Model_URL = 'http://127.0.0.1:11436'
$env:Model_Name = $selection.name
$env:CONTEXT_TOKENS = '4096'
& $python manage.py runserver 127.0.0.1:8000
