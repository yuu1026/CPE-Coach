$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:HINT_MODE = 'live'
$env:OLLAMA_URL = 'http://127.0.0.1:11436'
$env:OLLAMA_MODEL = 'Qwen3-4B-Instruct-2507'
$env:CONTEXT_TOKENS = '4096'
& '.\.venv\Scripts\python.exe' manage.py runserver 127.0.0.1:8000
