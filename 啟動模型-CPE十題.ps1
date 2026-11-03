$ErrorActionPreference = 'Stop'
Write-Warning '專案已切換為 Gemma 3 4B IT 基礎模型；原十題 Qwen Adapter 無法沿用。此舊入口會轉交新版啟動腳本。'
& (Join-Path $PSScriptRoot '啟動模型.ps1')
