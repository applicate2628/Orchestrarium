param(
  [string]$Path
)

$patterns = @(
  'AKIA[0-9A-Z]{16}'
  'ghp_[A-Za-z0-9]{36}'
  'sk-[A-Za-z0-9]{20,}'
  'Bearer[[:space:]]+[A-Za-z0-9._~+/=-]+'
  '[Pp]assword[[:space:]]*[:=]'
  '[Ss]ecret[[:space:]]*[:=]'
  '[Tt]oken[[:space:]]*[:=]'
  'api[_-]?[Kk]ey[[:space:]]*[:=]'
  '[A-Za-z]:\\\\Users\\\\'
  '/Users/'
  '/home/'
  '/private/var/folders/'
  '/var/folders/'
  '^Human:[[:space:]]*'
  '^Assistant:[[:space:]]*'
  '^\$[[:space:]]+'
  '^>>>[[:space:]]+'
  '\[[0-9]{2}:[0-9]{2}:[0-9]{2}\]'
)

$gitArgs = @(
  'grep'
  '-n'
  '-I'
  '-E'
  '--full-name'
)

foreach ($pattern in $patterns) {
  $gitArgs += @('-e', $pattern)
}

if ($Path) {
  $gitArgs += @('--no-index', '--', $Path)
} else {
  $gitArgs += @('--cached', '--', '.')
}

$env:GIT_PAGER = 'cat'
$scanOutput = & git --no-pager @gitArgs 2>&1
$exitCode = $LASTEXITCODE
$selfPattern = '^scripts/check-publication-safety\.(ps1|sh):'

if ($exitCode -eq 0) {
  $filtered = @($scanOutput | Where-Object { $_ -notmatch $selfPattern })
  if ($filtered.Count -gt 0) {
    $filtered
    Write-Error 'publication-safety scan found potential tracked-content leak markers'
    exit 1
  }

  exit 0
}

if ($exitCode -eq 1) {
  exit 0
}

exit $exitCode
