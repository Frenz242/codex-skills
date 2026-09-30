# Run: powershell -NoProfile -File tests/test_installer_launcher.ps1
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../install.ps1')
$script:calls = [System.Collections.Generic.List[object]]::new()
function wsl.exe {
    $script:calls.Add(@($args))
    $global:LASTEXITCODE = 0
    if ($args[0] -eq '--list') { return "Ubuntu`0", "Debian`0" }
    if ($args[3] -eq 'wslpath') { return '/mnt/c/installer with spaces/install.sh' }
    $global:LASTEXITCODE = 7
}
$found = @(Get-WslDistributions)
if ($found.Count -ne 2 -or $found[0] -ne 'Ubuntu') { throw 'Distribution decoding failed' }
$Target = 'Ubuntu'
$InstallerArguments = @('--dest', '/home/example/custom skills', '--list')
$result = Invoke-SkillInstaller
if ($result -ne 7) { throw 'WSL exit code was not preserved' }
$call = $script:calls[$script:calls.Count - 1]
if ($call[4] -ne '/mnt/c/installer with spaces/install.sh' -or $call[6] -ne '/home/example/custom skills') {
    throw 'WSL paths/arguments were split or lost'
}
$Target = 'Unknown'
try { Invoke-SkillInstaller; throw 'Expected unknown distro rejection' }
catch { if ($_.Exception.Message -notlike 'WSL distribution not found:*') { throw } }
function wsl.exe { throw 'WSL feature unavailable' }
if (@(Get-WslDistributions).Count -ne 0) { throw 'Missing WSL should not block native Windows' }
Write-Host 'PASS: WSL enumeration, null decoding, dispatch, paths, exit code and unknown target.'
