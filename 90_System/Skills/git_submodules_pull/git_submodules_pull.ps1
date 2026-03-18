param(
  [Parameter(Mandatory = $false)]
  [ValidateSet("remote", "pinned")]
  [string]$Mode = "remote",

  [Parameter(Mandatory = $false)]
  [switch]$DryRun,

  [Parameter(Mandatory = $false)]
  [string]$RepoRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
  param([string]$ExplicitRepoRoot)
  if ($ExplicitRepoRoot -and $ExplicitRepoRoot.Trim().Length -gt 0) {
    return (Resolve-Path -LiteralPath $ExplicitRepoRoot).Path
  }
  # 90_System/Skills/git_submodules_pull -> repo root is 3 parents up.
  return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\\..\\..")).Path
}

function Invoke-Git {
  param(
    [string]$Cwd,
    [string[]]$GitArgs
  )

  $rendered = ($GitArgs | ForEach-Object { $_ }) -join " "
  Write-Host ("`$ git -C `"{0}`" {1}" -f $Cwd, $rendered)
  if ($DryRun) { return }

  & git -C $Cwd @GitArgs
  if ($LASTEXITCODE -ne 0) {
    throw ("git failed ({0}): git -C `"{1}`" {2}" -f $LASTEXITCODE, $Cwd, $rendered)
  }
}

$root = Resolve-RepoRoot -ExplicitRepoRoot $RepoRoot

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  throw "git not found on PATH"
}

$inside = (& git -C $root rev-parse --is-inside-work-tree 2>$null)
if ($LASTEXITCODE -ne 0 -or ($inside -as [string]).Trim().ToLowerInvariant() -ne "true") {
  throw "Not a git repo: $root"
}

$gitmodules = Join-Path $root ".gitmodules"
if (-not (Test-Path -LiteralPath $gitmodules)) {
  Write-Host "No .gitmodules found; nothing to do."
  exit 0
}

Invoke-Git -Cwd $root -GitArgs @("submodule", "sync", "--recursive")
Invoke-Git -Cwd $root -GitArgs @("submodule", "update", "--init", "--recursive")

if ($Mode -eq "remote") {
  Invoke-Git -Cwd $root -GitArgs @("submodule", "update", "--remote", "--merge", "--recursive")
}

Invoke-Git -Cwd $root -GitArgs @("submodule", "status", "--recursive")
Invoke-Git -Cwd $root -GitArgs @("status", "-sb")
