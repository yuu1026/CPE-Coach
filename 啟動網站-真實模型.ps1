$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
. (Join-Path $PSScriptRoot '啟動共用.ps1')
$env:HINT_MODE = 'live'
$env:Model_URL = 'http://127.0.0.1:11436'
$env:Model_Name = 'gemma-3-4b-it'
$env:CONTEXT_TOKENS = '4096'
& (Get-CpePython) manage.py runserver 127.0.0.1:8000
