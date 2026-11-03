$ErrorActionPreference = 'Stop'
Write-Warning '專案已切換為 Gemma；原 Qwen Adapter 無法沿用。此舊入口會轉交目前預設模型的啟動腳本。'
& (Join-Path $PSScriptRoot '啟動模型.ps1')
