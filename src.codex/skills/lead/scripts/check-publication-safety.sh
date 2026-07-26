#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash <path>/check-publication-safety.sh
  bash <path>/check-publication-safety.sh --path <dir>

By default, scans staged tracked files in the repository for publication-safety issues.
Use --path only for local fixture testing or explicit manual checks.
EOF
}

scan_path="."
scan_mode="tracked"

if [[ $# -gt 0 ]]; then
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --path)
      shift
      if [[ $# -eq 0 ]]; then
        echo "error: --path requires a path argument" >&2
        exit 2
      fi
      scan_path="$1"
      scan_mode="path"
      shift
      ;;
    *)
      scan_path="$1"
      scan_mode="path"
      shift
      ;;
  esac
fi

if [[ $# -gt 0 ]]; then
  echo "error: unexpected extra arguments: $*" >&2
  usage >&2
  exit 2
fi

# Non-path patterns: secrets, tokens, keys, .env, transcript markers, and
# macOS temp-dir markers. These are an UNCONDITIONAL block source -- they are
# NEVER passed through the placeholder allowlist. A line that matches any of
# these BLOCKS even if it also contains an allowed path token (e.g. a secret on
# a line that also mentions C:\Users\<you>).
#
# The machine-local PATH patterns (Windows/MSYS/macOS user homes, dev/work
# roots) are intentionally NOT in this array. They are placeholder-bearing
# (`C:\Users\<name>`, `%USERPROFILE%`, `C:\Users\you`) and are handled below by
# the allowlist-aware path check, which reuses the single allowlist owner
# (`check-machine-local-path.py`'s find_machine_paths) so placeholder docs do
# not false-positive while concrete machine paths still block.
nonpath_patterns=(
  'AKIA[0-9A-Z]{16}'
  'ghp_[A-Za-z0-9]{36}'
  'sk-[A-Za-z0-9]{20,}'
  'sk-ant-[A-Za-z0-9_-]{20,}'
  'ANTHROPIC_[A-Z_]*(KEY|TOKEN)[^[:alnum:]_]?[[:space:]]*[:=]'
  'Bearer[[:space:]]+[A-Za-z0-9._~+/=-]+'
  # The next 4 entries (password/secret/token/api-key) test the VALUE, not just
  # the variable name -- fixed 2026-07-26 after a false-positive reproduction:
  # unanchored `[Tt]oken[[:space:]]*[:=]` matched the tail of the C#
  # PARAMETER NAME `cancellationToken` in `CancellationToken cancellationToken
  # = default`, because "Token" sits right before "=" with no leak present.
  # Independent hardenings, all POSIX ERE (git grep -E: no \b, no (?:...), no
  # lookaround, no backreferences):
  #   1. Left-anchor group `((^|[^A-Za-z])X|[a-z]X)` requires the keyword to
  #      start at an identifier-segment boundary: start-of-line, a non-letter
  #      char (`_`, `-`, `.`, digit, space, punctuation -- covers
  #      access_token / API_KEY / auth-token), OR a lower->upper camelCase
  #      transition (covers apiToken / myApiKey). This rejects the keyword as
  #      an incidental substring of an unrelated word (`myatoken`, `mistoken`)
  #      while still catching AUTH_TOKEN (a pre-existing false-negative this
  #      widening also closes: the old `[Tt]oken` was case-sensitive on
  #      "oken" and never matched all-caps TOKEN at all).
  #   2. Value-shape alternation after `[:=]` requires either a QUOTED literal
  #      (see #3 below) or a BARE literal containing a digit with >=5 chars on
  #      one side of it (floor: 6 total chars, verified against the shortest
  #      real fixture in this file's own test corpus, `password: hunter2`).
  #      This is what actually rejects `cancellationToken = default` (and
  #      null/None/nil/undefined/"" /end-of-line): none of those keywords
  #      contain a digit, and a member access (`config.ApiKey`) or call
  #      (`GetTokenAsync(ct)`) is truncated by the `.`/`(` before the
  #      digit-or-length requirement can be met. BARE requires a digit as an
  #      extra signal, so 6 chars is enough -- shorter would re-admit short
  #      English words that happen to contain a digit -- BUT the digit must
  #      fall with >=5 chars on ONE side, so a digit sitting near the CENTER
  #      of a short value pushes the EFFECTIVE floor to 10, not 6: `abc3def`
  #      and `abcd5efgh` (7/9 chars, digit centered) stay clean, `abcd5efghi`
  #      (10 chars) blocks -- all three verified against this file's own test
  #      corpus. This asymmetric-floor consequence is recorded here rather
  #      than left implicit; it is not itself a fix target.
  #   3. QUOTED (revised 2026-07-27 to close two false-negative regressions
  #      reproduced by $security-reviewer):
  #      a. Quote-STYLE blind spot. The quoted branch used to match a LITERAL
  #         `"` only. A `'` or `` ` `` is not in the bare alphabet either, so
  #         `token = '<20 random chars>'` passed CLEAN regardless of length or
  #         digit content -- a real false-negative regression, not a
  #         documented tradeoff (single-quoted strings are Python's idiomatic
  #         style, and Python is this repo's own hook language). Fixed by
  #         matching a DELIMITER CLASS instead of a literal quote character
  #         (originally `[^[:alnum:][:space:]]`, anything neither
  #         alphanumeric nor whitespace, on both sides of the value --
  #         narrowed again the same day, see 3.c below, so this paragraph
  #         describes the MECHANISM, not the current class literal). This is
  #         load-bearing, not stylistic: a bash single-quoted array literal
  #         has NO way to embed a literal `'` without ending the literal
  #         early -- doing so would break this exact catalog entry's own
  #         "entire line is one single-quoted literal, no interior `'`"
  #         shape, which is what lets `is_intentional_scanner_regex_line`
  #         (bash, below) and its Python mirror `_is_intentional_scanner_line`
  #         (further below) recognize it as an intentional pattern-catalog
  #         line during the scanner's self-scan. So this pattern could never
  #         spell a `'`-delimiter directly; the class sidesteps that by never
  #         needing the literal character in its own source text, while
  #         still matching it at runtime. The two delimiters matched are not
  #         required to be the SAME punctuation character (POSIX ERE, as run
  #         by `git grep -E`, has no backreference to enforce that), so a
  #         mismatched pair like `token = 'value"` also matches -- accepted,
  #         since a mismatched pair only widens which delimiter SHAPES are
  #         recognized as quoting, it does not by itself admit any new
  #         character into the class. That is a narrower claim than "the
  #         delimiter mechanism only widens the catch set" -- the class
  #         itself (which characters count as a delimiter at all) is a
  #         separate axis, and on THAT axis the original class over-widened
  #         and had to be narrowed back down (3.c).
  #      b. Quoted-short-secret gap. Inside the delimiters, a flat >=12-char
  #         run of the quote alphabet (`[A-Za-z0-9_./+=-]`, no digit required
  #         -- this is what keeps this repo's own illustrative leak example,
  #         `token = "ghp_xxxx"` (8 chars, digit-free), clean) used to be the
  #         ONLY accepted shape, so a quoted value below that floor was clean
  #         EVEN WITH A DIGIT PRESENT: `password = "Summ3r2024"` (10 chars)
  #         passed while the identical BARE value `password = Summ3r2024`
  #         blocked -- quoting a real secret made it disappear, an incoherent
  #         wire shape. Fixed by adding the SAME 5-chars-one-side-of-a-digit
  #         BARE shape as a second accepted shape inside the delimiters.
  #      c. Delimiter-class over-breadth (found by $security-reviewer round 2,
  #         over 15 rows, 13 blocking -- fixed same day as 3.a/3.b, which is
  #         why this is 3.c and not a new top-level item). The class from 3.a,
  #         `[^[:alnum:][:space:]]`, matches far more than quote characters:
  #         it also matches identifier and statement punctuation --
  #         `_ ( [ { < . / ; , -`. C-family/scripting code supplies a
  #         CLOSING member of that set for free, so any value that starts
  #         with one of those and contains a conforming digit-bearing run
  #         ending at another punctuation character satisfied the "delimited
  #         value" shape with NO quote involved at all -- re-creating, through
  #         a route no fixture covered, the exact name-not-value defect this
  #         item was admitted to fix. Measured false positives, none
  #         containing a secret: `apiKey = _configuration.ApiKey;` (idiomatic
  #         C# dependency injection -- the admission fixture
  #         `config.ApiKey` only stayed clean because `config` has no leading
  #         `_`), `token = _refreshTokenValue;`, `password: /run/secrets/db_
  #         password` (an ordinary k8s/compose file path), and
  #         `api_key = <YOUR_API_KEY>` (a documentation placeholder). Fixed
  #         by narrowing the class to
  #         `[^][:alnum:][:space:]_.,;:(){}<>/+=~-]` (POSIX bracket-expression
  #         position rules: leading `]` and trailing `-` are both literal
  #         members of the set, not stray syntax) on BOTH delimiter
  #         occurrences. This excludes alphanumerics, whitespace, and
  #         `_ . , ; : ( ) { } < > / + = ~ -`, leaving `" ' `` ! @ # $ % ^ & *
  #         ? |` as the matchable delimiters -- still every quoting style 3.a
  #         was about, none of the punctuation a C-family/scripting
  #         identifier or statement supplies. Measured zero detection loss:
  #         the false-positive corpus dropped from 13-of-15 blocked to 2 (the
  #         survivors are `expiry_token = "2024-01-01"`, a genuinely quoted
  #         digit-bearing value that IS this catalog's intended shape, and
  #         `password = --force-with-lease12`, which matches through the
  #         pre-existing bare-value branch and is unrelated to the delimiter
  #         class); the anchor and quote-hole corpora (3.a/3.b) kept an
  #         identical catch set; the original 41-line reproduction corpus
  #         kept exact 20/20 parity. All measured against this file's own
  #         fixture corpora with `git grep`-compatible ERE.
  #
  # Known, undisclosed-until-now alphabet limit (left OPEN, NOT fixed here --
  # widening the alphabet is a design decision with real false-positive cost,
  # not an in-place fix): both the quoted and bare alphabets above cover only
  # `[A-Za-z0-9_./+=-]`. A secret containing `@ : $ ! % ~ #`, an embedded
  # space, or a non-ASCII byte is invisible to this catalog UNLESS a
  # conforming run of sufficient length also sits in the same value --
  # `P@ssw0rd1234567`, a `$2b$12$...` bcrypt hash, and a `user:pass@host`
  # URL-embedded credential all measure clean today.
  '((^|[^A-Za-z])[Pp]|[a-z]P)[Aa][Ss][Ss][Ww][Oo][Rr][Dd][[:space:]]*[:=][[:space:]]*([^][:alnum:][:space:]_.,;:(){}<>/+=~-]([A-Za-z0-9_./+=-]{12,}|[A-Za-z0-9_./+=-]{5,}[0-9][A-Za-z0-9_./+=-]*|[A-Za-z0-9_./+=-]*[0-9][A-Za-z0-9_./+=-]{5,})[^][:alnum:][:space:]_.,;:(){}<>/+=~-]|[A-Za-z0-9_+/=-]{5,}[0-9][A-Za-z0-9_+/=-]*|[A-Za-z0-9_+/=-]*[0-9][A-Za-z0-9_+/=-]{5,})'
  '((^|[^A-Za-z])[Ss]|[a-z]S)[Ee][Cc][Rr][Ee][Tt][[:space:]]*[:=][[:space:]]*([^][:alnum:][:space:]_.,;:(){}<>/+=~-]([A-Za-z0-9_./+=-]{12,}|[A-Za-z0-9_./+=-]{5,}[0-9][A-Za-z0-9_./+=-]*|[A-Za-z0-9_./+=-]*[0-9][A-Za-z0-9_./+=-]{5,})[^][:alnum:][:space:]_.,;:(){}<>/+=~-]|[A-Za-z0-9_+/=-]{5,}[0-9][A-Za-z0-9_+/=-]*|[A-Za-z0-9_+/=-]*[0-9][A-Za-z0-9_+/=-]{5,})'
  '((^|[^A-Za-z])[Tt]|[a-z]T)[Oo][Kk][Ee][Nn][[:space:]]*[:=][[:space:]]*([^][:alnum:][:space:]_.,;:(){}<>/+=~-]([A-Za-z0-9_./+=-]{12,}|[A-Za-z0-9_./+=-]{5,}[0-9][A-Za-z0-9_./+=-]*|[A-Za-z0-9_./+=-]*[0-9][A-Za-z0-9_./+=-]{5,})[^][:alnum:][:space:]_.,;:(){}<>/+=~-]|[A-Za-z0-9_+/=-]{5,}[0-9][A-Za-z0-9_+/=-]*|[A-Za-z0-9_+/=-]*[0-9][A-Za-z0-9_+/=-]{5,})'
  '((^|[^A-Za-z])[Aa]|[a-z]A)[Pp][Ii][_-]?[Kk][Ee][Yy][[:space:]]*[:=][[:space:]]*([^][:alnum:][:space:]_.,;:(){}<>/+=~-]([A-Za-z0-9_./+=-]{12,}|[A-Za-z0-9_./+=-]{5,}[0-9][A-Za-z0-9_./+=-]*|[A-Za-z0-9_./+=-]*[0-9][A-Za-z0-9_./+=-]{5,})[^][:alnum:][:space:]_.,;:(){}<>/+=~-]|[A-Za-z0-9_+/=-]{5,}[0-9][A-Za-z0-9_+/=-]*|[A-Za-z0-9_+/=-]*[0-9][A-Za-z0-9_+/=-]{5,})'
  'BEGIN RSA PRIVATE KEY'
  'BEGIN OPENSSH PRIVATE KEY'
  'BEGIN PRIVATE KEY'
  'private_key'
  'secret_key'
  '/private/var/folders/'
  '/var/folders/'
  '^Human:[[:space:]]*'
  '^Assistant:[[:space:]]*'
  '^\$[[:space:]]+'
  '^>>>[[:space:]]+'
  '\[[0-9]{2}:[0-9]{2}:[0-9]{2}\]'
)

# Refined approach-A path patterns, used ONLY in the no-Python fallback. They
# require a real-name character ([A-Za-z0-9_]) right after the root separator,
# which strips the `<...>` / `%...%` / `${...}` / `...` placeholder
# false-positives that the original placeholder-blind patterns flagged. Unlike
# the Python path (approach B), these do NOT honor the bare example-token
# allowlist, so the fallback over-blocks `C:\Users\you` etc. -- a deliberate
# fail-safe (over-block) when the shared allowlist owner is unreachable. POSIX
# ERE only (git grep -E): plain (a|b) groups, no (?:...).
fallback_path_patterns=(
  '[A-Za-z]:[\\/]+[Uu]sers[\\/]+[A-Za-z0-9_]'
  '[A-Za-z]:[\\/]+(dev|work|projects)[\\/]+[A-Za-z0-9_]'
  '/[A-Za-z]/[Uu]sers/[A-Za-z0-9_]'
  '/[A-Za-z]/(dev|work|projects)/[A-Za-z0-9_]'
  '/home/[A-Za-z0-9_]'
  '/Users/[A-Za-z0-9_]'
)

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

# Resolve the single allowlist owner RELATIVE to THIS scanner's own location,
# so each pack imports its own sibling copy and never the other pack's. The
# reference module adds its sibling scripts/ dir to sys.path for hook_common, so
# importing the module file directly is sufficient.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ref_module="$script_dir/../hooks/check-machine-local-path.py"

if [[ "$scan_mode" == "tracked" ]]; then
  staged_paths=()
  regular_staged_paths=()
  scanner_staged_paths=()
  while IFS= read -r -d '' staged_path; do
    staged_paths+=("$staged_path")
    if [[ "$staged_path" == *"/check-publication-safety.sh" || "$staged_path" == "check-publication-safety.sh" ]]; then
      scanner_staged_paths+=("$staged_path")
    else
      regular_staged_paths+=("$staged_path")
    fi
  done < <(git diff --cached --name-only --diff-filter=ACMRTUXB -z --)

  if [[ ${#staged_paths[@]} -eq 0 ]]; then
    # Honest-result signal (2026-07-26 hardening, D2 of
    # work-items/backlog/2026-07-25-push-gate-blind-to-scan-result/brief.md
    # §11.5): an empty `git diff --cached` is NOT a clean scan, it is a scan
    # that examined NOTHING -- the exact shape of the ordinary commit-then-push
    # flow, where the staged index already equals HEAD. Exit 0 is still correct
    # (there is nothing here to block on), but the caller consuming this
    # scan's RESULT (check-git-push-gate.py step 8 branch (b)) must be able to
    # tell this apart from a real clean scan, so it never counts an empty scan
    # as a pass. This line is deliberately tagged "tracked" with a "0" count so
    # SCAN_CLEAN_TRACKED_REGEX's `[1-9]\d*` requirement cannot match it.
    echo "publication-safety: clean (tracked, examined 0 files -- nothing staged)"
    exit 0
  fi
  scan_files=("${staged_paths[@]}")
else
  scan_files=("$scan_path")
fi

path_name_block=0
for scan_file in "${scan_files[@]}"; do
  base_name="${scan_file##*/}"
  if [[ "$base_name" == ".env" ]]; then
    echo "$scan_file: blocked filename .env (staged secret/config file)" >&2
    path_name_block=1
  fi
  # The pack's own credential file (.claude/SECRET.md or any SECRET.md) must
  # never be staged, regardless of content format -- this filename block is the
  # format-independent primary defense; the sk-ant-/ANTHROPIC_ content patterns
  # above are the secondary net. The name compare is CASE-INSENSITIVE: Windows,
  # the pack's primary platform, has a case-insensitive filesystem, so a staged
  # secret.md / Secret.md is the same credential file and must block identically.
  name_upper="$(printf '%s' "$base_name" | tr '[:lower:]' '[:upper:]')"
  if [[ "$name_upper" == "SECRET.MD" ]]; then
    echo "$scan_file: blocked filename $base_name (staged credential file; keep it untracked)" >&2
    path_name_block=1
  fi
done

# Self-exemption for the scanner's OWN staged copy only -- callers key it to
# the check-publication-safety.sh filename, so it can never exempt any other
# staged file. The scanner file IS the pattern catalog, so exactly two of its
# own line shapes are intentional marker-bearing content: (1) a pattern-array
# entry, i.e. a line that is ENTIRELY one single-quoted literal, and (2) a
# full-line comment (scanner documentation naming the markers it blocks).
# Anything else in the scanner file still blocks -- a catalog line with a
# trailing payload, or code carrying a real value, is not exempt.
is_intentional_scanner_regex_line() {
  local trimmed="${1#"${1%%[![:space:]]*}"}"
  trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
  local q="'"
  if [[ ${#trimmed} -ge 2 && "$trimmed" == "$q"*"$q" && "${trimmed:1:${#trimmed}-2}" != *"$q"* ]]; then
    return 0
  fi
  [[ "$trimmed" == "#"* ]]
}

# Build the non-path git grep command (unconditional block source).
nonpath_cmd=(git grep -n -I -E --full-name)
for pattern in "${nonpath_patterns[@]}"; do
  nonpath_cmd+=(-e "$pattern")
done
if [[ "$scan_mode" == "tracked" ]]; then
  if [[ ${#regular_staged_paths[@]} -gt 0 ]]; then
    nonpath_cmd+=(--cached -- "${regular_staged_paths[@]}")
  else
    nonpath_cmd=()
  fi
else
  nonpath_cmd+=(--no-index -- "$scan_path")
fi

# MSYS2_ARG_CONV_EXCL='*' disables MSYS path conversion of git-grep arguments.
# Without it, the bundled Windows gate bash rewrites leading-slash patterns
# (e.g. /var/folders/) into Windows paths, so they silently match nothing. It
# is safe for every pattern (grep patterns are not real paths).
set +e
if [[ ${#nonpath_cmd[@]} -gt 0 ]]; then
  MSYS2_ARG_CONV_EXCL='*' "${nonpath_cmd[@]}"
  nonpath_status=$?
else
  nonpath_status=1
fi
set -e

# nonpath_status: 0 = a non-path leak marker was found (BLOCK); 1 = none; >=2 =
# git error -> fail safe by propagating the error status below.
nonpath_block=0
if [[ $nonpath_status -eq 0 ]]; then
  nonpath_block=1
fi
if [[ "$scan_mode" == "tracked" && ${#scanner_staged_paths[@]} -gt 0 ]]; then
  scanner_nonpath_cmd=(git grep -n -I -E --full-name)
  for pattern in "${nonpath_patterns[@]}"; do
    scanner_nonpath_cmd+=(-e "$pattern")
  done
  scanner_nonpath_cmd+=(--cached -- "${scanner_staged_paths[@]}")
  set +e
  scanner_nonpath_output="$(MSYS2_ARG_CONV_EXCL='*' "${scanner_nonpath_cmd[@]}")"
  scanner_nonpath_status=$?
  set -e
  if [[ $scanner_nonpath_status -eq 0 ]]; then
    while IFS= read -r scanner_line; do
      [[ -z "$scanner_line" ]] && continue
      if [[ "$scanner_line" =~ ^([^:]+):([0-9]+):(.*)$ ]]; then
        scanner_content="${BASH_REMATCH[3]}"
        if is_intentional_scanner_regex_line "$scanner_content"; then
          continue
        fi
      fi
      echo "$scanner_line" >&2
      nonpath_block=1
    done <<< "$scanner_nonpath_output"
  elif [[ $scanner_nonpath_status -ge 2 ]]; then
    echo "publication-safety: scanner-file nonpath grep failed (status $scanner_nonpath_status); over-blocking" >&2
    nonpath_block=1
  fi
fi

# Path check: prefer approach B (Python allowlist owner, immune to MSYS argv
# mangling, honors the placeholder/example-token allowlist). Fall back to
# approach A (refined ERE under the MSYS guard) only when no Python interpreter
# is reachable. Fail safe = over-block; never fail open.
python_bin=""
if command -v python3 >/dev/null 2>&1; then
  python_bin="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  python_bin="$(command -v python)"
fi

path_block=0
if [[ -n "$python_bin" && -f "$ref_module" ]]; then
  set +e
  "$python_bin" - "$ref_module" "$scan_mode" "${scan_files[@]}" <<'PUBSAFE_PATHFILTER_PY'
import importlib.util
import os
import subprocess
import sys


def _load_find_machine_paths(mod_file):
    spec = importlib.util.spec_from_file_location("_mlp_ref", mod_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.find_machine_paths


def _staged_content(path):
    out = subprocess.run(["git", "show", ":" + path], capture_output=True)
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", errors="replace")


def _disk_content(path):
    try:
        with open(path, "rb") as fh:
            return fh.read().decode("utf-8", errors="replace")
    except (OSError, UnicodeError):
        return None


def _expand_path_mode(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, names in os.walk(p):
                for name in names:
                    yield os.path.join(root, name)
        else:
            yield p


SCANNER_BASENAME = "check-publication-safety.sh"


def _is_intentional_scanner_line(line):
    # Mirror of the shell-side self-exemption, applied ONLY to a file whose
    # basename is the scanner's own (checked by the caller): a pattern-array
    # entry (a line that is entirely one single-quoted literal) or a full-line
    # comment. Every other file gets no exemption, so a leaked machine-local
    # path in any non-scanner file still blocks.
    trimmed = line.strip()
    if trimmed.startswith("#"):
        return True
    return (
        len(trimmed) >= 2
        and trimmed.startswith("'")
        and trimmed.endswith("'")
        and "'" not in trimmed[1:-1]
    )


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("pubsafe path filter: missing reference module / mode\n")
        return 1
    mod_file, mode, raw_files = argv[0], argv[1], argv[2:]
    try:
        find_machine_paths = _load_find_machine_paths(mod_file)
    except Exception as exc:
        sys.stderr.write(
            f"pubsafe path filter: cannot load allowlist owner {mod_file!r}: {exc}; over-blocking\n"
        )
        return 1
    files = list(raw_files) if mode == "tracked" else list(_expand_path_mode(raw_files))
    blocking = 0
    for path in files:
        is_scanner_file = os.path.basename(path) == SCANNER_BASENAME
        content = _staged_content(path) if mode == "tracked" else _disk_content(path)
        if content is None:
            sys.stderr.write(
                f"pubsafe path filter: could not read {mode} content for {path!r}; over-blocking\n"
            )
            blocking += 1
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            if is_scanner_file and _is_intentional_scanner_line(line):
                continue
            hits = find_machine_paths(line)
            if hits:
                blocking += 1
                sys.stderr.write(f"{path}:{lineno}: machine-local path: {', '.join(hits[:5])}\n")
    return 1 if blocking else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:
        sys.stderr.write(f"pubsafe path filter: unexpected error: {exc}; over-blocking\n")
        sys.exit(1)
PUBSAFE_PATHFILTER_PY
  path_status=$?
  set -e
  if [[ $path_status -ne 0 ]]; then
    path_block=1
  fi
else
  echo "publication-safety: no Python interpreter reachable (or allowlist owner missing); using refined regex fallback (degraded mode -- example-token paths over-block)" >&2
  fallback_cmd=(git grep -n -I -E --full-name)
  for pattern in "${fallback_path_patterns[@]}"; do
    fallback_cmd+=(-e "$pattern")
  done
  if [[ "$scan_mode" == "tracked" ]]; then
    fallback_cmd+=(--cached -- "${scan_files[@]}")
  else
    fallback_cmd+=(--no-index -- "$scan_path")
  fi
  set +e
  MSYS2_ARG_CONV_EXCL='*' "${fallback_cmd[@]}"
  fallback_status=$?
  set -e
  # 0 = a concrete machine path was found (BLOCK); 1 = none; >=2 = git error.
  if [[ $fallback_status -eq 0 ]]; then
    path_block=1
  elif [[ $fallback_status -ge 2 ]]; then
    echo "publication-safety: fallback git grep failed (status $fallback_status); over-blocking" >&2
    path_block=1
  fi
fi

if [[ $path_name_block -eq 1 || $nonpath_block -eq 1 || $path_block -eq 1 ]]; then
  echo "publication-safety scan found potential tracked-content leak markers" >&2
  exit 1
fi

# No leaks found by either check. If the non-path git grep returned an
# unexpected error status (>=2), propagate it as a fail-safe rather than
# reporting a clean pass.
if [[ $nonpath_status -ge 2 ]]; then
  exit "$nonpath_status"
fi

# Honest-result signal (2026-07-26 hardening, see the matching comment on the
# tracked-mode empty-set exit above): report the scan MODE and the actual
# examined count so a caller reading this scan's own output (not just its exit
# code) can tell a real, non-empty, tracked-mode clean pass apart from an
# empty-set pass or a `--path` fixture-testing pass. `scan_mode` is printed
# verbatim ("tracked" or "path") -- deliberately NOT normalized to one word --
# so a `--path` invocation can never read as "tracked" gate evidence
# (check-git-push-gate.py's SCAN_CLEAN_TRACKED_REGEX requires the literal word
# "tracked").
#
# examined_count for `path` mode is NOT `${#scan_files[@]}` (that array always
# holds exactly one entry: the `--path` argument itself, whether it names a
# file or a directory) -- it is the ACTUAL number of files examined, computed
# the same way the Python allowlist path (`_expand_path_mode`) walks a
# directory. Reporting a hardcoded "1" for a directory argument that in fact
# contained several files would be a false record of what was scanned (an
# honesty defect flagged 2026-07-26; path mode can never satisfy the gate
# regardless of count, so this was never a security hole, only a wrong number).
if [[ "$scan_mode" == "path" ]]; then
  if [[ -d "$scan_path" ]]; then
    examined_count="$(find "$scan_path" -type f | wc -l | tr -d '[:space:]')"
  else
    examined_count=1
  fi
else
  examined_count="${#scan_files[@]}"
fi
examined_word="files"
if [[ "$examined_count" -eq 1 ]]; then
  examined_word="file"
fi
echo "publication-safety: clean (${scan_mode}, examined ${examined_count} ${examined_word})"
exit 0
