# Abacus.AI Skill Auto-Installer - Windows PowerShell bootstrap
#   irm https://raw.githubusercontent.com/Turkishmadaraa/abacus-skill-installer/main/install.ps1 | iex
# With arguments:
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/Turkishmadaraa/abacus-skill-installer/main/install.ps1))) anthropics/skills@pdf
$ErrorActionPreference = "Stop"
$Repo = if ($env:SKILL_INSTALLER_REPO) { $env:SKILL_INSTALLER_REPO } else { "Turkishmadaraa/abacus-skill-installer" }
$Raw = "https://raw.githubusercontent.com/$Repo/main/auto_install.py"

$Py = $null
foreach ($c in @("python", "python3", "py")) {
    if (Get-Command $c -ErrorAction SilentlyContinue) { $Py = $c; break }
}
if (-not $Py) { Write-Error "Python 3.8+ bulunamadı. https://www.python.org/downloads/ adresinden kurun."; exit 1 }

$Tmp = Join-Path $env:TEMP "auto_install.py"
Invoke-WebRequest -UseBasicParsing -Uri $Raw -OutFile $Tmp
$env:PYTHONIOENCODING = "utf-8"
if ($args.Count -eq 0) {
    & $Py $Tmp "https://github.com/$Repo/tree/main"
    & $Py $Tmp --profile
} else {
    & $Py $Tmp @args
}
Remove-Item $Tmp -ErrorAction SilentlyContinue
