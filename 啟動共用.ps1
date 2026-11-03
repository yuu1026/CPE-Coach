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
