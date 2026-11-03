function Get-CpePython {
    param([ValidateSet('Model', 'Website')][string]$Purpose = 'Model')
    $modules = if ($Purpose -eq 'Model') { 'torch,transformers,accelerate,bitsandbytes' } else { 'django,httpx' }
    $probe = "import importlib.util,sys; sys.exit(0 if all(importlib.util.find_spec(n) is not None for n in sys.argv[1].split(',')) else 1)"
    $candidates = @()
    if ($env:CPE_PYTHON) {
        if (-not (Test-Path -LiteralPath $env:CPE_PYTHON)) { throw 'CPE_PYTHON 指定的 Python 不存在。' }
        & $env:CPE_PYTHON -c $probe $modules 2>$null
        if ($LASTEXITCODE -ne 0) { throw "CPE_PYTHON 缺少 $Purpose 所需套件：$modules" }
        Write-Host "使用 Python：$env:CPE_PYTHON"
        return $env:CPE_PYTHON
    }
    if ($env:CONDA_PREFIX) { $candidates += Join-Path $env:CONDA_PREFIX 'python.exe' }
    # Discover the named environment without depending on conda activate/profile hooks.
    $roots = @((Join-Path $HOME 'miniconda3'), (Join-Path $HOME 'anaconda3'), (Join-Path $HOME 'miniforge3'))
    foreach ($command in @('python', 'conda')) {
        $entry = Get-Command $command -ErrorAction SilentlyContinue
        if ($entry -and $entry.Source -and (Test-Path -LiteralPath $entry.Source)) {
            $directory = [IO.Path]::GetDirectoryName($entry.Source)
            for ($level = 0; $level -lt 4 -and $directory; $level++) {
                $roots += $directory
                $directory = [IO.Path]::GetDirectoryName($directory)
            }
        }
    }
    foreach ($root in ($roots | Select-Object -Unique)) { $candidates += Join-Path $root 'envs/cpe-ai/python.exe' }
    $candidates += Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    $pathPython = Get-Command python -ErrorAction SilentlyContinue
    if ($pathPython) { $candidates += $pathPython.Source }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not $candidate -or -not (Test-Path -LiteralPath $candidate)) { continue }
        & $candidate -c $probe $modules 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "使用 Python：$candidate"
            return $candidate
        }
    }
    throw "找不到具備 $modules 的 Python。請在已安裝套件的環境執行，或設定 CPE_PYTHON 指向該 python.exe。"
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
