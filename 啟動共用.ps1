function Get-CpePython {
    if ($env:CPE_PYTHON) { return $env:CPE_PYTHON }
    if ($env:CONDA_PREFIX) {
        $condaPython = Join-Path $env:CONDA_PREFIX 'python.exe'
        if (Test-Path -LiteralPath $condaPython) { return $condaPython }
    }
    $venvPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    if (Test-Path -LiteralPath $venvPython) { return $venvPython }
    return (Get-Command python -ErrorAction Stop).Source
}

function Get-CpeExperiment {
    param([ValidateSet('v1', 'v2')][string]$Version = 'v2')
    $adapterPath = Join-Path $PSScriptRoot "training/runs/gemma3-cpe49-$Version"
    $reportPath = Join-Path $adapterPath 'training_report.json'
    if (-not (Test-Path -LiteralPath $reportPath) -or -not (Test-Path -LiteralPath (Join-Path $adapterPath 'adapter_model.safetensors'))) {
        throw '找不到已完成的本地實驗 Adapter，請先依 training/CPE49.md 訓練。'
    }
    $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
    if ($report.smoke_only -or $report.topics -ne 49 -or $report.optimizer_steps -ne $report.expected_steps -or $report.optimizer_steps -le 0) {
        throw '此實驗版本尚未完成完整訓練。'
    }
    return [pscustomobject]@{name="gemma-3-4b-cpe49-experimental-$Version"; adapter_path=$adapterPath}
}
