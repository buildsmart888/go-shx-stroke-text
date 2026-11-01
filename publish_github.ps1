# Create a public repository for this exact release using the authenticated GitHub CLI.
# Run from PowerShell after installing Git and gh, and signing in: gh auth login
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'Install GitHub CLI: https://cli.github.com/' }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Install Git for Windows.' }
& gh auth status
if ($LASTEXITCODE -ne 0) { throw 'Sign in first: gh auth login' }
& gh repo view buildsmart888/go-shx-stroke-text --json name >$null 2>$null
if ($LASTEXITCODE -ne 0) {
  & gh repo create buildsmart888/go-shx-stroke-text --public --description 'Native SHX/SHP stroke fonts for IngeTrazo Model and Sheet Composer' --source . --remote origin --push
  if ($LASTEXITCODE -ne 0) { throw 'Unable to create or push the repository.' }
} else {
  & git remote get-url origin >$null 2>$null
  if ($LASTEXITCODE -ne 0) { & git remote add origin 'https://github.com/buildsmart888/go-shx-stroke-text.git' }
  & git push -u origin main
  if ($LASTEXITCODE -ne 0) { throw 'Push failed.' }
}
& git push origin v0.2.0
if ($LASTEXITCODE -ne 0) { throw 'Tag push failed.' }
Write-Host 'Published: https://github.com/buildsmart888/go-shx-stroke-text' -ForegroundColor Green
Write-Host 'Verify raw ZIP and its SHA-256 before opening a catalog PR.'
