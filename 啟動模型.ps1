$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:HF_MODEL_PATH = 'C:\Users\tt\models\Qwen3-4B-Instruct-2507'
& '.\.venv\Scripts\python.exe' local_model_server.py
