param([ValidateSet('v1', 'v2')][string]$Version = 'v2')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
. (Join-Path $PSScriptRoot '啟動共用.ps1')
Assert-CpePortAvailable -Port 8000
$selection = Get-CpeExperiment -Version $Version
$env:HINT_MODE = 'live'
$env:Model_URL = 'http://127.0.0.1:11436'
$env:Model_Name = $selection.name
$env:CONTEXT_TOKENS = '4096'
& (Get-CpePython -Purpose Website) manage.py runserver 127.0.0.1:8000
