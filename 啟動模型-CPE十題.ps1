$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:HF_MODEL_PATH = 'C:\Users\tt\models\Qwen3-4B-Instruct-2507'
$env:HF_ADAPTER_PATH = Join-Path $PSScriptRoot 'training/runs/cpe10-v1'
$env:HF_SERVE_MODEL_NAME = 'Qwen3-4B-CPE10-v1'
& 'C:\Users\tt\miniconda3\envs\cpe-ai\python.exe' local_model_server.py
