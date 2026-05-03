[CmdletBinding(PositionalBinding = $false)]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]] $Arguments
)

$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path $PSScriptRoot 'agent-run-ledger.py'
if (-not (Test-Path -LiteralPath $scriptPath)) {
  throw "Unable to locate agent-run-ledger.py next to $PSCommandPath."
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  $python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $python) {
  throw "Unable to locate python or py."
}

& $python.Source $scriptPath @Arguments
exit $LASTEXITCODE
