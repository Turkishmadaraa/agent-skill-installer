# Agent Skill Installer - bootstrap for Windows PowerShell
#   irm https://raw.githubusercontent.com/Turkishmadaraa/agent-skill-installer/main/install.ps1 | iex
# With arguments:
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/Turkishmadaraa/agent-skill-installer/main/install.ps1))) anthropics/skills@pdf --agent claude-code
# Pin a release: $env:SKILL_INSTALLER_REF = "v2.0.0"
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Repo = "Turkishmadaraa/agent-skill-installer"
$Ref = if ($env:SKILL_INSTALLER_REF) { $env:SKILL_INSTALLER_REF } else { "main" }
if ($Ref -notmatch '^[A-Za-z0-9._/-]+$' -or $Ref -match '\.\.') { throw "Geçersiz SKILL_INSTALLER_REF" }
$Raw = "https://raw.githubusercontent.com/$Repo/$Ref/skills/installing-agent-skills/auto_install.py"

$Py = $null
foreach ($c in @("python", "python3", "py")) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notmatch 'WindowsApps\\python') { $Py = $c; break }
}
if (-not $Py) { throw "Python 3.8+ bulunamadı. https://www.python.org/downloads/ adresinden kurun." }

$Dir = Join-Path ([IO.Path]::GetTempPath()) ("skill-installer-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $Dir | Out-Null
try {
    $Tmp = Join-Path $Dir "auto_install.py"
    Invoke-WebRequest -UseBasicParsing -Uri $Raw -OutFile $Tmp
    $env:PYTHONIOENCODING = "utf-8"
    if ($args.Count -eq 0) {
        & $Py $Tmp "https://github.com/$Repo/tree/$Ref"
    } else {
        & $Py $Tmp @args
    }
} finally {
    Remove-Item -Recurse -Force $Dir -ErrorAction SilentlyContinue
}
