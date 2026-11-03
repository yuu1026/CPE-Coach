param([ValidateSet('v1', 'v2')][string]$Version = 'v2')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
. (Join-Path $PSScriptRoot '啟動共用.ps1')
$selection = Get-CpeExperiment -Version $Version
Write-Warning '這是未設為預設的實驗版，抽查仍有定位不準或題意誤述；請配合實際測試結果比較。'
if (-not $env:HF_MODEL_PATH) { $env:HF_MODEL_PATH = Join-Path $PSScriptRoot 'models/gemma-3-4b-it' }
$env:HF_USE_BASE_MODEL = '0'
$env:HF_SERVE_MODEL_NAME = $selection.name
$env:HF_ADAPTER_PATH = $selection.adapter_path
& (Get-CpePython) local_model_server.py
