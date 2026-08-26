$ErrorActionPreference = "Stop"
$feedbackStore = Join-Path $PSScriptRoot "feedback_store.py"
$pythonCandidates = [System.Collections.Generic.List[object]]::new()

function Add-PythonCandidate {
    param(
        [string]$Command,
        [string[]]$PrefixArguments = @()
    )

    if (-not [string]::IsNullOrWhiteSpace($Command)) {
        $pythonCandidates.Add([pscustomobject]@{
            Command = $Command
            PrefixArguments = $PrefixArguments
        })
    }
}

Add-PythonCandidate -Command $env:CODEX_SKILL_PYTHON

if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
    $bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path -LiteralPath $bundledPython -PathType Leaf) {
        Add-PythonCandidate -Command $bundledPython
    }
}

foreach ($candidateName in @("py", "python3", "python")) {
    $resolved = Get-Command $candidateName -ErrorAction SilentlyContinue
    if ($null -ne $resolved) {
        $prefixArguments = if ($candidateName -eq "py") { @("-3") } else { @() }
        Add-PythonCandidate -Command $resolved.Source -PrefixArguments $prefixArguments
    }
}

foreach ($candidate in $pythonCandidates) {
    try {
        & $candidate.Command @($candidate.PrefixArguments) -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" *> $null
        if ($LASTEXITCODE -ne 0) {
            continue
        }

        & $candidate.Command @($candidate.PrefixArguments) $feedbackStore @args
        exit $LASTEXITCODE
    }
    catch {
        continue
    }
}

[Console]::Error.WriteLine(
    "feedback-store launcher: no supported Python 3 interpreter found; set CODEX_SKILL_PYTHON to a Python 3 executable."
)
exit 127
