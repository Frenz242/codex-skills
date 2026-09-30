# Run with: powershell -NoProfile -File .\install.ps1
[CmdletBinding()]
param(
    [string]$Target,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$InstallerArguments
)
$ErrorActionPreference = 'Stop'

function Get-WslDistributions {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { return }
    try { $output = & wsl.exe --list --quiet 2>$null }
    catch { return } # Windows PowerShell 5.1 throws on native stderr with Stop.
    if ($LASTEXITCODE -eq 0) {
        $output | ForEach-Object { ($_ -replace "`0", '').Trim() } | Where-Object { $_ }
    }
}

function Invoke-SkillInstaller {
    $distributions = @(Get-WslDistributions)
    if (-not $Target) {
        Write-Host 'Install/update target:'
        Write-Host ' 1. Native Windows (current user)'
        for ($i = 0; $i -lt $distributions.Count; $i++) {
            Write-Host " $($i + 2). WSL: $($distributions[$i]) (default Linux user; Codex detection runs there)"
        }
        $choice = Read-Host 'Choose target [1], or q to quit'
        if ($choice -eq 'q') { return 0 }
        if (-not $choice) { $choice = '1' }
        $index = 0
        if (-not [int]::TryParse($choice, [ref]$index) -or $index -lt 1 -or $index -gt ($distributions.Count + 1)) {
            throw 'Invalid target selection.'
        }
        $Target = if ($index -eq 1) { 'windows' } else { $distributions[$index - 2] }
    }
    if ($Target -ne 'windows') {
        if ($Target -notin $distributions) { throw "WSL distribution not found: $Target" }
        # wslpath and --exec preserve spaces and avoid injecting paths into shell code.
        $linuxScript = & wsl.exe --distribution $Target --exec wslpath -a (Join-Path $PSScriptRoot 'install.sh')
        if ($LASTEXITCODE -ne 0) { throw 'Cannot map the installer into WSL; run install.sh inside the distribution.' }
        & wsl.exe --distribution $Target --exec sh "$linuxScript" @InstallerArguments | Out-Host
        return $LASTEXITCODE
    }
    $candidates = @()
    if ($env:CODEX_SKILL_PYTHON) { $candidates += ,@($env:CODEX_SKILL_PYTHON) }
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundled) { $candidates += ,@($bundled) }
    foreach ($name in @('py', 'python3', 'python')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            if ($name -eq 'py') { $candidates += ,@($command.Source, '-3') }
            else { $candidates += ,@($command.Source) }
        }
    }
    foreach ($candidate in $candidates) {
        $command = $candidate[0]
        $prefix = @($candidate | Select-Object -Skip 1)
        try {
            & $command @prefix -c 'import sys; sys.exit(sys.version_info < (3, 10))' *> $null
            if ($LASTEXITCODE -ne 0) { continue }
        } catch { continue }
        & $command @prefix (Join-Path $PSScriptRoot 'scripts\install_skills.py') @InstallerArguments | Out-Host
        return $LASTEXITCODE
    }
    throw 'Python 3.10+ is required. Install it or set CODEX_SKILL_PYTHON to its executable.'
}

if ($MyInvocation.InvocationName -ne '.') {
    try { exit (Invoke-SkillInstaller) }
    catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }
}
