$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
. (Join-Path $PSScriptRoot '啟動共用.ps1')
if (-not $env:HF_MODEL_PATH) { $env:HF_MODEL_PATH = Join-Path $PSScriptRoot 'models/gemma-3-4b-it' }
$env:HF_SERVE_MODEL_NAME = 'gemma-3-4b-it'
Remove-Item Env:HF_ADAPTER_PATH -ErrorAction SilentlyContinue
& (Get-CpePython) local_model_server.py
