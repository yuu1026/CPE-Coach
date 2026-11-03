$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:HINT_MODE = 'live'
$env:Model_URL = 'http://127.0.0.1:11436'
$env:Model_Name = 'Qwen3-4B-CPE10-v1'
$env:CONTEXT_TOKENS = '4096'
& 'C:\Users\tt\miniconda3\envs\cpe-ai\python.exe' manage.py runserver 127.0.0.1:8000
