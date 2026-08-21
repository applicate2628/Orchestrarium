"""Structural guard for the "$lead is a role held BY the main conversation" invariant.

Two prior REVISE cycles kept finding lead-vs-main-conversation SPLIT residues in
ever-new textual forms (backticks, "main session" vs "conversation", slashes) that
narrow greps missed one at a time. This test converts "hope the grep caught
everything" into a build gate: it scans the shipped packs and FAILS if it finds
either

  (a) a dispatch-of-lead phrasing   -> $lead treated as a spawnable subagent, or
  (b) a split-owner duality         -> $lead and the main conversation presented as
                                       TWO owners/participants, or a LIVE
                                       `orchestrator: main|lead` field / "template,
                                       orchestrator" frontmatter list (the retired
                                       field that encoded that duality).

WRONG (this test fails on it):
  - "`$lead`/main-conv move it", "the lead or main session", "main session or lead"
  - the same split with an and/both/vs joiner: "`$lead` and main-conv",
    "both the lead and the main session", "lead vs main conversation"
  - "closing role / `$lead`", "orchestrator: lead" as a LIVE field
  - "subagent_type: lead" as a live dispatch, "You are the `lead` subagent",
    "spawn/dispatch/invoke `$lead`", "`$lead` ... spawned/dispatched"

FINE (allow-listed — this test must stay green on it):
  - "$lead" as a bare ROLE NAME held by the main conversation
  - "the main conversation (as Lead)", "the main session IS the lead",
    "hold the Lead role AS the main conversation"
  - explicitly LABELED legacy notes with a read-mapping ("legacy", "renamed",
    "older `status.md` ...")
  - the fail-closed refusal stub's own negation/refusal lines
    ("is never spawned", "is not a dispatch target", "fail-closed", ...)

The allow-list is CATEGORY-SCOPED (see _ALLOW_GROUP_EXCUSES): it may excuse a
duality/field hit, but dispatch:* polarity is always decided around the exact
forbidden occurrence. A refusal elsewhere on the line can never neutralize it.

Scope: src.claude, src.codex, src.gemini, src.qwen, shared, docs. NOT work-items /
.scratch / changelogs / dated-plan snapshots (those legitimately record superseded
relations).
"""

from __future__ import annotations

import re
from collections import Counter
from enum import Enum, auto
from typing import NamedTuple
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Shipped-pack trees only. work-items/, .scratch/, changelogs, and dated-plan
# snapshots are excluded (see _is_excluded) because recording a superseded
# relation there is legitimate provenance, not a live split.
SCAN_DIRS = ("src.claude", "src.codex", "src.gemini", "src.qwen", "shared", "docs")

TEXT_SUFFIXES = {".md", ".sh", ".ps1", ".py", ".yaml", ".yml", ".toml", ".json", ".txt"}

# Path segments / shapes that are out of scope for the live-tree invariant.
_EXCLUDED_PARTS = {
    "work-items",
    ".scratch",
    ".git",
    "__pycache__",
    "node_modules",
    "archive",
    "_archive",
    "legacy",
    "plans",  # dated plan snapshots live under .../plans/
}
_DATED_BASENAME = re.compile(r"^\d{4}-\d{2}-\d{2}")
_CHANGELOG_BASENAME = re.compile(r"^(RELEASE_NOTES|CHANGELOG|HISTORY)", re.IGNORECASE)


def _is_excluded(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if parts & _EXCLUDED_PARTS:
        return True
    if _DATED_BASENAME.match(path.name):  # e.g. 2026-05-03-agent-execution-tracking.md
        return True
    if _CHANGELOG_BASENAME.match(path.name):
        return True
    return False


# --- FORBIDDEN patterns -------------------------------------------------------
# Each entry: (name, compiled regex). A line hitting any of these is a violation
# UNLESS an allow-list pattern also matches that line.
FORBIDDEN = [
    # (a) dispatch-of-lead: $lead treated as a spawnable subagent
    ("dispatch:subagent_type-lead", re.compile(r"subagent_type:\s*`?\*?lead\b", re.IGNORECASE)),
    ("dispatch:you-are-lead-subagent", re.compile(r"you are the\s+`?lead`?\s+subagent", re.IGNORECASE)),
    (
        "dispatch:verb-lead",
        # "both"/"either" cover the joiner form "spawn both `$lead` and X" (F26):
        # dispatching $lead alongside a real subagent is still a dispatch of $lead.
        re.compile(
            r"\b(?:dispatch|spawn|launch|invoke)(?:ed|s|ing)?\s+(?:(?:both|either)\s+)?(?:a\s+|an\s+|the\s+)?`?\$lead\b",
            re.IGNORECASE,
        ),
    ),
    (
        "dispatch:lead-spawned",
        re.compile(r"\$lead`?[^.\n]{0,20}?\b(?:spawned|dispatched|invoked as a subagent)\b", re.IGNORECASE),
    ),
    # (b) split-owner duality: $lead and the main conversation as TWO owners
    (
        "duality:lead-slash-main",
        re.compile(r"\$?lead`?\s*/\s*`?\*?main[- ]?(?:conv|conversation|session)", re.IGNORECASE),
    ),
    (
        "duality:main-slash-lead",
        re.compile(r"main[- ]?(?:conv|conversation|session)`?\s*/\s*`?\$?lead\b", re.IGNORECASE),
    ),
    ("duality:lead-or-main", re.compile(r"\blead\s+or\s+main\b", re.IGNORECASE)),
    ("duality:main-or-lead", re.compile(r"\bmain[- ]?(?:conv\w*|session)\s+or\s+`?\$?lead\b", re.IGNORECASE)),
    ("duality:role-slash-lead", re.compile(r"\brole\s*/\s*`?\$?lead\b", re.IGNORECASE)),
    # (b) the same split with an and/both/vs joiner ("/" and "or" rephrased). The
    # "both the lead and the main session" form is covered by lead-and-main (the
    # "lead and (the) main" core is a substring of the both-form). Joiners are
    # matched with \s+ only — a HYPHENATED "lead-vs-main" is meta-prose ABOUT the
    # retired split (e.g. a doc describing this very guard), not a split assertion.
    ("duality:lead-and-main", re.compile(r"\blead`?\s+and\s+(?:the\s+)?`?\*?main\b", re.IGNORECASE)),
    ("duality:main-and-lead", re.compile(r"\bmain[- ]?(?:conv\w*|session)\s+and\s+(?:the\s+)?`?\$?lead\b", re.IGNORECASE)),
    ("duality:lead-vs-main", re.compile(r"\blead`?\s+vs\.?\s+(?:the\s+)?`?\$?main\b", re.IGNORECASE)),
    ("duality:main-vs-lead", re.compile(r"\bmain[- ]?(?:conv\w*|session)?\s+vs\.?\s+(?:the\s+)?`?\$?lead\b", re.IGNORECASE)),
    # (b) the retired duality-encoding frontmatter field
    ("field:orchestrator-value", re.compile(r"orchestrator:\s*(?:main|lead)\b", re.IGNORECASE)),
    ("field:template-orchestrator", re.compile(r"template,\s*orchestrator\b", re.IGNORECASE)),
]

# --- ALLOWLIST ----------------------------------------------------------------
# Each entry is (group, regex). A match no longer skips ALL forbidden checks on the
# line: it only excuses the forbidden CATEGORIES its group maps to in
# _ALLOW_GROUP_EXCUSES below. This is the F27 fix — the previous flat any-match let
# one incidental generic word ("legacy", "retired", "refuses") neutralize a REAL
# dispatch-of-lead reintroduction on the same line, contradicting this list's own
# stated design property. Entries stay SPECIFIC where they excuse dispatch hits
# (never a bare `\blead\b`, never a bare generic label word).
ALLOWLIST = [
    # unified-owner: $lead is the ROLE the main conversation holds (never two owners)
    ("unified-owner", re.compile(r"main conversation \(as lead\)", re.IGNORECASE)),
    ("unified-owner", re.compile(r"main conversation,? as lead", re.IGNORECASE)),
    ("unified-owner", re.compile(r"main conv \(as lead\)", re.IGNORECASE)),
    ("unified-owner", re.compile(r"main session \(as lead\)", re.IGNORECASE)),
    ("unified-owner", re.compile(r"main (?:codex )?session is the lead", re.IGNORECASE)),
    ("unified-owner", re.compile(r"the main conversation holds", re.IGNORECASE)),
    ("unified-owner", re.compile(r"main conversation'?s? orchestration role", re.IGNORECASE)),
    ("unified-owner", re.compile(r"orchestration role the main conversation holds", re.IGNORECASE)),
    ("unified-owner", re.compile(r"hold(?:ing|s)?\s+(?:the\s+)?(?:lead\s+role|`?\$?lead`?)", re.IGNORECASE)),
    # explicitly LABELED legacy / rename notes with a read-mapping. GENERIC words:
    # they may excuse a duality/field mention on the labeled line, NEVER a dispatch.
    ("legacy-label", re.compile(r"\blegacy\b", re.IGNORECASE)),
    ("legacy-label", re.compile(r"\brenamed\b", re.IGNORECASE)),
    ("legacy-label", re.compile(r"\bretired\b", re.IGNORECASE)),
    ("legacy-label", re.compile(r"older\s+`?status\.md", re.IGNORECASE)),
    ("legacy-label", re.compile(r"refus(?:e|es|al|ed)", re.IGNORECASE)),
    # Fail-closed refusal / negation lines may excuse duality and retired-field
    # wording. Dispatch polarity is handled occurrence-locally below.
    ("refusal-negation", re.compile(r"never\s+(?:itself\s+)?(?:be\s+)?spawn", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"never\s+spawns\s+a\s+separate", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"is never spawned", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"\bnot\s+spawn", re.IGNORECASE)),  # "do not spawn `$lead`" is the correct instruction
    ("refusal-negation", re.compile(r"not\s+(?:a\s+)?(?:dispatch|subagent)", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"never\s+(?:be\s+)?a\s+dispatch", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"not a subagent you spawn", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"never\s+(?:invoke|launch)\s+`?\$lead\b", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"fail-?closed", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"fails\s+closed", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"throwaway lead", re.IGNORECASE)),
]

# Which non-dispatch forbidden CATEGORIES each allow-list group may excuse.
# Dispatch is deliberately absent: the exact-occurrence classifier owns its polarity.
_ALLOW_GROUP_EXCUSES = {
    "unified-owner": frozenset({"duality", "field"}),
    "legacy-label": frozenset({"duality", "field"}),
    "refusal-negation": frozenset({"duality", "field"}),
}

class _DispatchPolarity(Enum):
    REFUSED = auto()
    POSITIVE_OR_UNPROVEN = auto()


class _TokenKind(Enum):
    WORD = auto()
    LEAD = auto()
    SUBAGENT_TYPE = auto()
    PUNCTUATION = auto()
    QUOTE = auto()
    OTHER = auto()


class _Token(NamedTuple):
    kind: _TokenKind
    value: str
    start: int
    end: int


_TOKEN = re.compile(
    r"(?P<lead>\$lead)"
    r"|(?P<subagent>subagent_type)"
    r"|(?P<word>[A-Za-z]+(?:'[A-Za-z]+)?)"
    r"|(?P<punct>[,;:.!?()\[\]{}\-–—])"
    r"|(?P<quote>[`\"'“”‘’])"
    r"|(?P<other>\S)",
    re.IGNORECASE,
)
_BOUNDARY_PUNCTUATION = frozenset({",", ";", ":", ".", "?", "!", "–", "—"})
_PROPOSITION_WORDS = frozenset(
    {"but", "however", "yet", "then", "while", "whereas", "although", "because", "if", "unless", "before", "after"}
)
_COORDINATORS = frozenset({"and", "or"})
_AUXILIARIES = frozenset(
    {"do", "does", "did", "must", "shall", "should", "may", "can", "could", "would", "will"}
)
_DISPATCH_BARE = frozenset({"dispatch", "spawn", "launch", "invoke"})
_DISPATCH_GERUND = frozenset({"dispatching", "spawning", "launching", "invoking"})
_REFUSAL_PREDICATES = frozenset(
    {
        "reject", "rejects", "rejected", "rejecting",
        "refuse", "refuses", "refused", "refusing",
        "forbid", "forbids", "forbidden", "forbidding",
        "prohibit", "prohibits", "prohibited", "prohibiting",
        "disallow", "disallows", "disallowed", "disallowing",
        "avoid", "avoids", "avoided", "avoiding",
        "deny", "denies", "denied", "denying",
        "block", "blocks", "blocked", "blocking",
        "prevent", "prevents", "prevented", "preventing",
    }
)
_REFUSED_ADJECTIVES = frozenset(
    {"refused", "rejected", "forbidden", "prohibited", "disallowed", "denied", "blocked"}
)
_TARGET_BRIDGE = frozenset(
    {"a", "an", "the", "any", "stale", "invalid", "retired", "deprecated", "dispatched"}
)
_POST_TARGET_NOUNS = frozenset({"route", "routes", "dispatch", "invocation", "definition", "wrapper", "stub", "target"})
_COPULAS = frozenset({"is", "are", "was", "were", "be", "been", "being"})
_NEGATED_CONTRACTIONS = {
    "don't": ("do", "not"),
    "doesn't": ("does", "not"),
    "didn't": ("did", "not"),
    "mustn't": ("must", "not"),
    "shouldn't": ("should", "not"),
    "can't": ("can", "not"),
    "cannot": ("can", "not"),
    "couldn't": ("could", "not"),
    "won't": ("will", "not"),
    "wouldn't": ("would", "not"),
    "isn't": ("is", "not"),
    "aren't": ("are", "not"),
    "wasn't": ("was", "not"),
    "weren't": ("were", "not"),
}
_POSITIVE_ROUTING_PREDICATES = frozenset(
    {
        "accept", "accepts", "accepted", "accepting",
        "allow", "allows", "allowed", "allowing",
        "permit", "permits", "permitted", "permitting",
        "support", "supports", "supported", "supporting",
        "require", "requires", "required", "requiring",
        "dispatch", "dispatches", "dispatched", "dispatching",
        "spawn", "spawns", "spawned", "spawning",
        "launch", "launches", "launched", "launching",
        "invoke", "invokes", "invoked", "invoking",
    }
)


def _tokenize(line: str) -> tuple[_Token, ...]:
    kinds = {
        "lead": _TokenKind.LEAD,
        "subagent": _TokenKind.SUBAGENT_TYPE,
        "word": _TokenKind.WORD,
        "punct": _TokenKind.PUNCTUATION,
        "quote": _TokenKind.QUOTE,
        "other": _TokenKind.OTHER,
    }
    tokens = []
    for match in _TOKEN.finditer(line):
        kind = kinds[match.lastgroup]
        value = match.group(0).casefold()
        if kind is _TokenKind.WORD and value in _NEGATED_CONTRACTIONS:
            # Keep the source span on both logical words: the classifier is
            # still span-bound to the forbidden match, while the normalizer
            # can reason about a contraction as its ordinary complement.
            tokens.extend(_Token(_TokenKind.WORD, word, *match.span()) for word in _NEGATED_CONTRACTIONS[value])
        else:
            tokens.append(_Token(kind, value, *match.span()))
    return tuple(tokens)


def _is_word(token: _Token) -> bool:
    return token.kind in {_TokenKind.WORD, _TokenKind.LEAD, _TokenKind.SUBAGENT_TYPE}


def _word_value(token: _Token) -> str:
    return "lead" if token.kind is _TokenKind.LEAD else token.value


def _word_tokens(tokens: tuple[_Token, ...], start: int, end: int) -> tuple[_Token, ...]:
    return tuple(token for token in tokens if _is_word(token) and start <= token.start and token.end <= end)


def _is_boundary(token: _Token) -> bool:
    return (
        token.kind is _TokenKind.PUNCTUATION and token.value in _BOUNDARY_PUNCTUATION
    ) or (token.kind is _TokenKind.WORD and token.value in _PROPOSITION_WORDS)


def _proposition_span(tokens: tuple[_Token, ...], hit: re.Match[str], line_length: int) -> tuple[int, int]:
    start = 0
    end = line_length
    for token in tokens:
        if not _is_boundary(token):
            continue
        if token.end <= hit.start():
            start = token.end
        elif token.start >= hit.end():
            end = token.start
            break
    return start, end


def _governor_is_negated(words: tuple[_Token, ...], index: int) -> bool:
    values = tuple(_word_value(token) for token in words)
    if index >= 1 and values[index - 1] == "never":
        return True
    if index >= 2 and values[index - 1] == "not" and values[index - 2] in (_AUXILIARIES | _COPULAS):
        return True
    if index >= 3 and values[index - 2 : index] == ("not", "be") and values[index - 3] in _AUXILIARIES:
        return True
    return index >= 2 and values[index - 2 : index] in (("fail", "to"), ("fails", "to"), ("failed", "to"))


def _direct_negation(words: tuple[_Token, ...], hit: re.Match[str]) -> bool:
    values = tuple(_word_value(token) for token in words)
    hit_indexes = [index for index, token in enumerate(words) if token.start < hit.end() and token.end > hit.start()]
    if not hit_indexes:
        return False
    first = hit_indexes[0]
    hit_values = values[first : hit_indexes[-1] + 1]
    if any(
        hit_values[index : index + 2] in (("never", "spawned"), ("not", "spawned"))
        for index in range(max(0, len(hit_values) - 1))
    ) or any(
        hit_values[index : index + 3] == ("not", "be", "spawned")
        for index in range(max(0, len(hit_values) - 2))
    ):
        return True
    if first >= 1 and values[first - 1] == "never":
        return first < 2 or values[first - 2] != "not"
    if first >= 1 and values[first - 1] == "without" and values[first] in _DISPATCH_GERUND:
        return first < 2 or values[first - 2] != "not"
    if values[first] in _DISPATCH_BARE and _governor_is_negated(words, first):
        return True
    return values[first] in _DISPATCH_GERUND and _governor_is_negated(words, first)


def _refusal_governed_target(words: tuple[_Token, ...], hit: re.Match[str]) -> bool:
    hit_indexes = [index for index, token in enumerate(words) if token.start < hit.end() and token.end > hit.start()]
    if not hit_indexes:
        return False
    index = hit_indexes[0] - 1
    while index >= 0 and _word_value(words[index]) in _TARGET_BRIDGE:
        index -= 1
    if index >= 0 and _word_value(words[index]) in _REFUSAL_PREDICATES:
        return not _governor_is_negated(words, index)
    return False


def _postposed_refusal(words: tuple[_Token, ...], hit: re.Match[str]) -> bool:
    values = tuple(_word_value(token) for token in words)
    hit_indexes = [index for index, token in enumerate(words) if token.start < hit.end() and token.end > hit.start()]
    if not hit_indexes:
        return False
    index = hit_indexes[-1] + 1
    while index < len(values) and values[index] in _POST_TARGET_NOUNS:
        index += 1
    suffix = values[index:]
    if suffix[:2] in (("fails", "closed"), ("fail", "closed")):
        return True
    if suffix[:3] in (("is", "fail", "closed"), ("are", "fail", "closed")):
        return True
    if len(suffix) >= 2 and suffix[0] in {"is", "are", "was", "were"} and suffix[1] in _REFUSED_ADJECTIVES:
        return True
    if len(suffix) >= 3 and suffix[:2] in (("must", "be"), ("should", "be")) and suffix[2] in _REFUSED_ADJECTIVES:
        return True
    if len(suffix) >= 3 and suffix[0] in _COPULAS and suffix[1:3] == ("never", "spawned"):
        return True
    if len(suffix) >= 3 and suffix[0] in _COPULAS and suffix[1:3] in (("not", "allowed"), ("not", "permitted")):
        return True
    if len(suffix) >= 3 and suffix[0] in _COPULAS and suffix[1:3] in (("not", "valid"), ("not", "supported")):
        return True
    return (
        len(suffix) >= 5 and suffix[0] in _COPULAS and suffix[1:5] == ("not", "a", "dispatch", "target")
    ) or (
        len(suffix) >= 4 and suffix[0] in _COPULAS and suffix[1:4] == ("not", "a", "subagent")
    )


def _metalinguistic_refusal(tokens: tuple[_Token, ...], hit: re.Match[str]) -> bool:
    colons = [token for token in tokens if token.kind is _TokenKind.PUNCTUATION and token.value == ":" and token.end <= hit.start()]
    if not colons:
        return False
    colon = colons[-1]
    left_start = 0
    for token in tokens:
        if token.end <= colon.start and _is_boundary(token) and token.value != ":":
            left_start = token.end
    words = _word_tokens(tokens, left_start, colon.start)
    if not words:
        return False
    index = len(words) - 1
    return _word_value(words[index]) in _REFUSAL_PREDICATES and not _governor_is_negated(words, index)


def _shared_negation(words: tuple[_Token, ...], hit: re.Match[str]) -> bool:
    values = tuple(_word_value(token) for token in words)
    hit_indexes = [index for index, token in enumerate(words) if token.start < hit.end() and token.end > hit.start()]
    if not hit_indexes:
        return False
    target_end = hit_indexes[-1]

    def consumes_groups(index: int, verb_set: frozenset[str]) -> bool:
        while index <= target_end:
            if values[index] not in verb_set:
                return False
            index += 1
            if index < len(values) and values[index] in {"a", "an", "the"}:
                index += 1
            if index >= len(values) or values[index] != "lead":
                return False
            index += 1
            if index > target_end:
                return True
            if values[index] not in _COORDINATORS:
                return False
            index += 1
        return False

    for index in range(target_end):
        if index + 2 <= target_end and values[index] in _AUXILIARIES and values[index + 1] == "not":
            if consumes_groups(index + 2, _DISPATCH_BARE):
                return True
        if values[index] in _REFUSAL_PREDICATES and not _governor_is_negated(words, index):
            if consumes_groups(index + 1, _DISPATCH_GERUND):
                return True
    return False


def _contradictory_continuation(words: tuple[_Token, ...], hit: re.Match[str]) -> bool:
    """Reject a proved refusal if the same proposition later reaffirms routing.

    The grammar deliberately stays conservative: after the exact target, an
    affirmative routing predicate in the same hard-terminator-bounded
    proposition is a contradiction. Negated routing and refusal-supporting
    predicates are excluded by the same normalizer used for the witness.
    """
    values = tuple(_word_value(token) for token in words)
    hit_indexes = [index for index, token in enumerate(words) if token.start < hit.end() and token.end > hit.start()]
    if not hit_indexes:
        return False
    for index in range(hit_indexes[-1] + 1, len(values)):
        # `dispatch` can also be a noun in "not a dispatch target" or
        # "lead dispatch is fail-closed".  A routing contradiction requires
        # the verb reading; a following copula or an article makes it a noun.
        is_dispatch_noun = values[index] == "dispatch" and (
            (index + 1 < len(values) and values[index + 1] in (_COPULAS | {"fail", "fails", "failed"}))
            or (index >= 1 and values[index - 1] in {"a", "an", "the"})
        )
        if (
            values[index] in _POSITIVE_ROUTING_PREDICATES
            and not is_dispatch_noun
            and not _governor_is_negated(words, index)
        ):
            return True
    return False


def _dispatch_occurrence_polarity(
    line: str, pattern_id: str, hit: re.Match[str]
) -> _DispatchPolarity:
    del pattern_id  # The stable ID stays an input contract; grammar binds the exact span.
    tokens = _tokenize(line)
    start, end = _proposition_span(tokens, hit, len(line))
    words = _word_tokens(tokens, start, end)
    shared = _shared_negation(words, hit)
    refused = (
        _direct_negation(words, hit)
        or _refusal_governed_target(words, hit)
        or _postposed_refusal(words, hit)
        or _metalinguistic_refusal(tokens, hit)
        or shared
    )
    return (
        _DispatchPolarity.REFUSED
        if refused and (shared or not _contradictory_continuation(words, hit))
        else _DispatchPolarity.POSITIVE_OR_UNPROVEN
    )


def _iter_files():
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if _is_excluded(path):
                continue
            yield path


def _line_verdict(line: str):
    """Return the forbidden-pattern name a line would trip, or None if clean/excused.

    Single owner of the verdict logic (the scan and the teeth tests both call it).
    An allow-list match excuses only the categories its group maps to in
    _ALLOW_GROUP_EXCUSES — a dispatch:* hit survives every generic label word.
    """
    excused: set[str] = set()
    for group, allow in ALLOWLIST:
        if allow.search(line):
            excused |= _ALLOW_GROUP_EXCUSES[group]
    for name, pat in FORBIDDEN:
        category = name.split(":", 1)[0]
        matches = tuple(pat.finditer(line))
        if not matches:
            continue
        if category == "dispatch":
            if any(
                _dispatch_occurrence_polarity(line, name, match)
                is _DispatchPolarity.POSITIVE_OR_UNPROVEN
                for match in matches
            ):
                return name
            continue
        if category not in excused:
            return name
    return None


def _scan():
    violations = []
    for path in _iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            name = _line_verdict(line)
            if name is not None:
                rel = path.relative_to(ROOT).as_posix()
                violations.append((rel, lineno, name, line.strip()))
    return violations


def test_no_lead_vs_main_conversation_split():
    violations = _scan()
    if violations:
        lines = "\n".join(
            f"  {rel}:{lineno}  [{name}]  {snippet}" for rel, lineno, name, snippet in violations
        )
        raise AssertionError(
            "lead-vs-main-conversation split residue detected "
            f"({len(violations)} line(s)). $lead is the orchestration role the MAIN "
            "CONVERSATION holds; it is never a second owner and never a dispatch target. "
            "Fix the residue, or (only for a genuine FINE form) extend the allow-list in "
            f"tests/test_lead_invariant.py:\n{lines}"
        )


# --- self-verifying teeth: the guard must fail on a reintroduced split -------
# These strings are the exact WRONG forms two REVISE cycles removed, plus the
# dispatch reintroductions the guard exists to block. (tests/ is out of scan
# scope, so these literals never self-trip the scan above.)
_KNOWN_SPLIT_FORMS = [
    "not straight to Active; `$lead`/main-conv move it Backlog -> Active when work starts.",
    "the lead or main session must prove which roles ran",
    "owned by the closing role / `$lead`, so the archivist does NOT decide",
    "YAML frontmatter (template, orchestrator, started, updated) and sections",
    "includes template, orchestrator role, active/completed agents, next action",
    "orchestrator: lead",
    "route it via `subagent_type: lead` to spin up the orchestrator",
    "You are the `lead` subagent; orchestrate the pipeline",
    "spawn a `$lead` subagent to coordinate the work",
    "run either the main session or `$lead` for this chain",
    "pick main-conv / `$lead` as the closing owner",
    # F26: the same split with the '/'-or-'or' joiner rephrased as and/both/vs —
    # a trivially rephrased reintroduction must not slip past the joiner list
    "`$lead` and main-conv move it Backlog -> Active when work starts.",
    "both the lead and the main session must prove which roles ran",
    "the main session and `$lead` co-own the closure step",
    "lead vs main conversation ownership is decided per item",
    # F27: real dispatch reintroductions carrying an incidental generic allow-list
    # word — the word may label a legacy note, it must never excuse a dispatch
    "spawn a `$lead` subagent to migrate the legacy status files",
    "dispatch `$lead` when the retired flow is requested",
    "invoke `$lead` if the user refuses the quick-fix template",
    # F26: dispatch of $lead ALONGSIDE a real subagent (both/either joiner)
    "spawn both $lead and the analyst",
    "spawn either `$lead` or the analyst for this chain",
]

# These FINE forms must stay clean — the allow-list must not be so tight that it
# flags a legitimate "$lead is the role the main conversation holds" statement.
_KNOWN_FINE_FORMS = [
    "the main conversation (as Lead) moves it Backlog -> Active when work starts.",
    "the main session (as Lead) must prove which roles ran",
    "owned by the closing role (the main conversation as Lead, or the capturing reviewer)",
    "YAML frontmatter (template, orchestration, started, updated) and sections",
    "includes template, orchestration weight, active/completed agents, next action",
    "`$lead` is the main conversation's orchestration role, never a spawned subagent",
    "Hold `$lead` as the orchestration role in the main Codex session; the main session IS the lead.",
    "You hold the Lead role AS the main conversation. `subagent_type: lead` is not a dispatch target.",
    "Legacy handling: older `status.md` files may carry `orchestrator: main | lead`; it is renamed.",
    "the main conversation holds the Lead role (activate the `/lead` skill); do not spawn `$lead`",
    "`$lead` / `$product-manager` consult open lessons when admitting similar work",
    # a refusal-stub line: the SPECIFIC negation phrase ("fails closed") may still
    # excuse the dispatch mention even though the generic "refused" alone may not
    "spawning `$lead` is refused: the stub fails closed and points to `/lead`",
]


def test_guard_flags_known_split_forms():
    misses = [s for s in _KNOWN_SPLIT_FORMS if _line_verdict(s) is None]
    assert not misses, f"guard failed to flag reintroduced split form(s): {misses}"


def test_guard_allows_negated_invoke_and_launch_of_lead():
    refusals = (
        "never invoke $lead",
        "never launch $lead",
    )
    false_positives = [(line, _line_verdict(line)) for line in refusals if _line_verdict(line) is not None]
    assert not false_positives, f"guard false-flagged lead refusal form(s): {false_positives}"


def test_negated_invoke_launch_allowlist_keeps_positive_dispatch_forbidden():
    positive_dispatches = (
        "invoke $lead to coordinate the work",
        "launch $lead to coordinate the work",
    )
    verdicts = [(line, _line_verdict(line)) for line in positive_dispatches]
    assert verdicts == [(line, "dispatch:verb-lead") for line in positive_dispatches]


def test_dispatch_polarity_is_scoped_to_each_forbidden_occurrence():
    """Catches refusal prose being treated as a live Lead dispatch, or vice versa."""
    cases = (
        (
            "the same definition rejects a stale dispatched `subagent_type: lead`",
            None,
        ),
        ("the wrapper refuses `subagent_type: lead` as an invalid route", None),
        ("the wrapper rejects: You are the `lead` subagent", None),
        ("the policy prohibits spawning `$lead` for orchestration", None),
        ("the policy avoids spawning `$lead` for orchestration", None),
        ("continue without spawning `$lead` for orchestration", None),
        ("`$lead` must not be spawned as a subagent", None),
        ("the stale route (`subagent_type: lead`) is refused", None),
        ("the `subagent_type: lead` dispatch fails closed", None),
        (
            "only a stale `subagent_type: lead` dispatch is fail-closed",
            None,
        ),
        (
            "You were dispatched through a stale route (`subagent_type: lead`). Do NOT orchestrate",
            "dispatch:subagent_type-lead",
        ),
        (
            "the wrapper accepts `subagent_type: lead` as a live dispatch",
            "dispatch:subagent_type-lead",
        ),
        ("the prompt says: You are the `lead` subagent", "dispatch:you-are-lead-subagent"),
        ("the policy requires spawning `$lead` for orchestration", "dispatch:verb-lead"),
        ("`$lead` is routinely spawned as a subagent", "dispatch:lead-spawned"),
        ("the active route (`subagent_type: lead`) is supported", "dispatch:subagent_type-lead"),
        ("the `subagent_type: lead` dispatch succeeds", "dispatch:subagent_type-lead"),
        ("the policy does not prohibit spawning `$lead`", "dispatch:verb-lead"),
        ("the wrapper fails to reject `subagent_type: lead`", "dispatch:subagent_type-lead"),
        ("the wrapper does not refuse: You are the `lead` subagent", "dispatch:you-are-lead-subagent"),
        (
            "invoke `$lead` if the user refuses the quick-fix template",
            "dispatch:verb-lead",
        ),
        ("do not dispatch the analyst; spawn `$lead`", "dispatch:verb-lead"),
        ("the legacy note is rejected, but invoke `$lead` now", "dispatch:verb-lead"),
    )

    observed = [(line, _line_verdict(line)) for line, _expected in cases]
    expected = [(line, verdict) for line, verdict in cases]
    assert observed == expected


def _assert_verdict_matrix(cases):
    mismatches = [
        (line, expected, observed)
        for line, expected in cases
        if (observed := _line_verdict(line)) != expected
    ]
    assert not mismatches, "dispatch polarity mismatch(es): " + repr(mismatches)


def test_ar1_unrelated_governor_counterexamples():
    _assert_verdict_matrix(
        (
            (
                "the wrapper rejects legacy status and invokes `$lead` now",
                "dispatch:verb-lead",
            ),
            ("without delay, spawn `$lead` for orchestration", "dispatch:verb-lead"),
            ("never mind the old route and spawn `$lead` as a subagent", "dispatch:verb-lead"),
            (
                "the wrapper refuses malformed input and accepts `subagent_type: lead` as live",
                "dispatch:subagent_type-lead",
            ),
            (
                "the policy does not dispatch analysts and spawns `$lead` as a subagent",
                "dispatch:verb-lead",
            ),
        )
    )


def test_ar_r2_counterexample_pair_matrix():
    _assert_verdict_matrix(
        (
            ("the stale route subagent_type: lead is active", "dispatch:subagent_type-lead"),
            ("the wrapper rejects the stale subagent_type: lead route", None),
            (
                "the stale route subagent_type: lead is accepted as live",
                "dispatch:subagent_type-lead",
            ),
            ("the stale subagent_type: lead route is refused", None),
            (
                "the wrapper never rejects: You are the lead subagent",
                "dispatch:you-are-lead-subagent",
            ),
            ("never dispatch $lead", None),
            (
                "the wrapper doesn't reject: You are the lead subagent",
                "dispatch:you-are-lead-subagent",
            ),
            ("the wrapper doesn't dispatch $lead", None),
            (
                "the wrapper cannot reject: You are the lead subagent",
                "dispatch:you-are-lead-subagent",
            ),
            ("the wrapper cannot dispatch $lead", None),
            (
                "the subagent_type: lead route is refused and accepted as live",
                "dispatch:subagent_type-lead",
            ),
            ("the subagent_type: lead route is refused and remains blocked", None),
            (
                "the wrapper rejects a stale subagent_type: lead and accepts it as live",
                "dispatch:subagent_type-lead",
            ),
            ("the wrapper rejects a stale subagent_type: lead and blocks it", None),
        )
    )


def test_stale_route_is_not_semantic_exemption():
    _assert_verdict_matrix(
        (
            (
                "You were dispatched through a stale route (subagent_type: lead). Do NOT orchestrate",
                "dispatch:subagent_type-lead",
            ),
            ("the stale route subagent_type: lead is active", "dispatch:subagent_type-lead"),
            (
                "the stale route subagent_type: lead is accepted as live",
                "dispatch:subagent_type-lead",
            ),
            ("stale route: lead or main owns the task", "duality:lead-or-main"),
            ("stale route: orchestrator: lead", "field:orchestrator-value"),
            ("the wrapper rejects the stale subagent_type: lead route", None),
            ("the stale subagent_type: lead route is refused", None),
            ("the stale route (subagent_type: lead) is refused", None),
        )
    )


def test_governor_complement_polarity_matrix():
    _assert_verdict_matrix(
        (
            ("never dispatch $lead", None),
            ("never reject: You are the lead subagent", "dispatch:you-are-lead-subagent"),
            ("do not dispatch $lead", None),
            ("do not reject: You are the lead subagent", "dispatch:you-are-lead-subagent"),
            ("does not dispatch $lead", None),
            ("does not reject: You are the lead subagent", "dispatch:you-are-lead-subagent"),
            ("did not dispatch $lead", None),
            ("did not reject: You are the lead subagent", "dispatch:you-are-lead-subagent"),
            ("must not dispatch $lead", None),
            ("must not reject: You are the lead subagent", "dispatch:you-are-lead-subagent"),
            ("should not dispatch $lead", None),
            ("should not reject: You are the lead subagent", "dispatch:you-are-lead-subagent"),
            ("cannot dispatch $lead", None),
            ("cannot reject: You are the lead subagent", "dispatch:you-are-lead-subagent"),
            ("fails to dispatch $lead", None),
            ("fails to reject: You are the lead subagent", "dispatch:you-are-lead-subagent"),
            ("failed to dispatch $lead", None),
            ("failed to reject: You are the lead subagent", "dispatch:you-are-lead-subagent"),
            ("continue without spawning $lead", None),
            ("continue not without spawning $lead", "dispatch:verb-lead"),
            ("never mind, dispatch $lead", "dispatch:verb-lead"),
            ("without delay, spawn $lead", "dispatch:verb-lead"),
            ("the subagent_type: lead route isn't refused", "dispatch:subagent_type-lead"),
            ("the subagent_type: lead route isn't allowed", None),
            ("the subagent_type: lead routes aren't refused", "dispatch:subagent_type-lead"),
            ("the subagent_type: lead routes aren't allowed", None),
            ("the subagent_type: lead route wasn't refused", "dispatch:subagent_type-lead"),
            ("the subagent_type: lead route wasn't allowed", None),
            ("the subagent_type: lead routes weren't refused", "dispatch:subagent_type-lead"),
            ("the subagent_type: lead routes weren't allowed", None),
            ("$lead isn't spawned as a subagent", None),
            ("$lead wasn't spawned as a subagent", None),
            *(case for contraction in ("don't", "doesn't", "didn't", "mustn't", "shouldn't", "can't", "couldn't", "won't", "wouldn't") for case in (
                (f"the wrapper {contraction} dispatch $lead", None),
                (
                    f"the wrapper {contraction} reject: You are the lead subagent",
                    "dispatch:you-are-lead-subagent",
                ),
            )),
        )
    )


def test_contradictory_continuation_matrix():
    _assert_verdict_matrix(
        (
            (
                "the subagent_type: lead route is refused and accepted as live",
                "dispatch:subagent_type-lead",
            ),
            ("the subagent_type: lead route is refused and remains blocked", None),
            ("the subagent_type: lead route is refused and is not accepted as live", None),
            ("the subagent_type: lead route is refused and cannot be invoked", None),
            (
                "the wrapper rejects a stale subagent_type: lead and accepts it as live",
                "dispatch:subagent_type-lead",
            ),
            ("the wrapper rejects a stale subagent_type: lead and blocks it", None),
            ("the wrapper rejects a stale subagent_type: lead and does not accept it", None),
            (
                "the wrapper rejects subagent_type: lead and accepts subagent_type: lead as live",
                "dispatch:subagent_type-lead",
            ),
            ("the wrapper rejects subagent_type: lead and rejects subagent_type: lead", None),
            (
                "the subagent_type: lead route is refused and supported as live",
                "dispatch:subagent_type-lead",
            ),
            ("the subagent_type: lead route is refused and prohibited", None),
            (
                "the wrapper rejects subagent_type: lead and accepts this route",
                "dispatch:subagent_type-lead",
            ),
            (
                "the wrapper rejects subagent_type: lead and permits that target",
                "dispatch:subagent_type-lead",
            ),
            (
                "the wrapper rejects subagent_type: lead and supports this dispatch",
                "dispatch:subagent_type-lead",
            ),
            (
                "the wrapper rejects subagent_type: lead and accepts",
                "dispatch:subagent_type-lead",
            ),
            ("the subagent_type: lead route is refused. Another route is accepted", None),
        )
    )


def test_qa1_punctuation_counterexamples():
    _assert_verdict_matrix(
        (
            ("do not spawn `$lead`, invoke `$lead` now", "dispatch:verb-lead"),
            ("do not spawn `$lead`: invoke `$lead` now", "dispatch:verb-lead"),
            ("do not spawn `$lead` — invoke `$lead` now", "dispatch:verb-lead"),
            ("do not spawn `$lead`, or invoke `$lead` now", "dispatch:verb-lead"),
        )
    )


def test_mixed_occurrence_polarity_matrix():
    _assert_verdict_matrix(
        (
            ("do not spawn `$lead` or invoke `$lead`", None),
            ("the policy prohibits spawning `$lead` and invoking `$lead`", None),
            ("do not spawn `$lead`, invoke `$lead` now", "dispatch:verb-lead"),
            ("spawn `$lead`, but do not invoke `$lead`", "dispatch:verb-lead"),
            ("spawn `$lead` and invoke `$lead`", "dispatch:verb-lead"),
        )
    )


def test_metalinguistic_refusal_pair_matrix():
    _assert_verdict_matrix(
        (
            ("the wrapper rejects: You are the `lead` subagent", None),
            (
                "the wrapper does not reject: You are the `lead` subagent",
                "dispatch:you-are-lead-subagent",
            ),
            ("the wrapper says: You are the `lead` subagent", "dispatch:you-are-lead-subagent"),
            ("the wrapper accepts: You are the `lead` subagent", "dispatch:you-are-lead-subagent"),
        )
    )


def test_coordinated_dispatch_scope_matrix():
    _assert_verdict_matrix(
        (
            ("do not spawn `$lead` or invoke `$lead`", None),
            ("the policy prohibits spawning `$lead` and invoking `$lead`", None),
            (
                "the policy does not dispatch analysts and spawns `$lead` as a subagent",
                "dispatch:verb-lead",
            ),
            (
                "the wrapper rejects malformed input and accepts `subagent_type: lead` as live",
                "dispatch:subagent_type-lead",
            ),
            ("do not spawn `$lead`; invoke `$lead` now", "dispatch:verb-lead"),
            ("do not spawn `$lead`. Invoke `$lead` now", "dispatch:verb-lead"),
            ("do not spawn `$lead`, but invoke `$lead` now", "dispatch:verb-lead"),
        )
    )


def test_double_negation_matrix():
    _assert_verdict_matrix(
        (
            ("the policy does not prohibit spawning `$lead`", "dispatch:verb-lead"),
            ("the wrapper fails to reject `subagent_type: lead`", "dispatch:subagent_type-lead"),
            (
                "the wrapper does not refuse: You are the `lead` subagent",
                "dispatch:you-are-lead-subagent",
            ),
            ("the policy is not without spawning `$lead`", "dispatch:verb-lead"),
            ("the `subagent_type: lead` route is not refused", "dispatch:subagent_type-lead"),
        )
    )


def test_quote_and_code_span_matrix():
    _assert_verdict_matrix(
        (
            ("spawn $lead", "dispatch:verb-lead"),
            ("`spawn $lead`", "dispatch:verb-lead"),
            ("'spawn $lead'", "dispatch:verb-lead"),
            ('"spawn $lead"', "dispatch:verb-lead"),
            ("(spawn $lead)", "dispatch:verb-lead"),
            ("do not spawn $lead", None),
            ("`do not spawn $lead`", None),
            ("'do not spawn $lead'", None),
            ('"do not spawn $lead"', None),
            ("(do not spawn $lead)", None),
            ('the wrapper rejects: "You are the lead subagent"', None),
            (
                'the wrapper says: "You are the lead subagent"',
                "dispatch:you-are-lead-subagent",
            ),
        )
    )


def test_direct_and_postposed_refusal_matrix():
    _assert_verdict_matrix(
        (
            ("do not spawn `$lead`", None),
            ("never invoke `$lead`", None),
            ("continue without spawning `$lead`", None),
            ("`$lead` must not be spawned as a subagent", None),
            ("the wrapper rejects a stale dispatched `subagent_type: lead`", None),
            ("`subagent_type: lead` is refused", None),
            ("the stale route (`subagent_type: lead`) is refused", None),
            ("the `subagent_type: lead` dispatch fails closed", None),
            ("`$lead` is never spawned as a subagent", None),
        )
    )


def test_dispatch_pattern_family_teeth():
    _assert_verdict_matrix(
        (
            ("the wrapper rejects a stale dispatched `subagent_type: lead`", None),
            (
                "the wrapper accepts `subagent_type: lead` as a live route",
                "dispatch:subagent_type-lead",
            ),
            ("the wrapper rejects: You are the `lead` subagent", None),
            ("the wrapper says: You are the `lead` subagent", "dispatch:you-are-lead-subagent"),
            ("do not spawn `$lead`", None),
            ("spawn `$lead`", "dispatch:verb-lead"),
            ("`$lead` is never spawned as a subagent", None),
            ("`$lead` is routinely spawned as a subagent", "dispatch:lead-spawned"),
        )
    )


def test_live_dispatch_corpus_is_exact_and_refused():
    occurrences = []
    for path in _iter_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            for name, pattern in FORBIDDEN:
                if not name.startswith("dispatch:"):
                    continue
                for hit in pattern.finditer(line):
                    occurrences.append(
                        (
                            path.relative_to(ROOT).as_posix(),
                            name,
                            _dispatch_occurrence_polarity(line, name, hit),
                        )
                    )

    assert Counter((path, name) for path, name, _polarity in occurrences) == Counter(
        {
            ("src.claude/CLAUDE.md", "dispatch:subagent_type-lead"): 2,
            ("src.claude/agents/lead.md", "dispatch:subagent_type-lead"): 2,
            ("src.claude/agents/lead.md", "dispatch:lead-spawned"): 1,
            ("src.claude/commands/agents-bugfix.md", "dispatch:verb-lead"): 1,
            ("src.claude/commands/agents-resume.md", "dispatch:verb-lead"): 1,
            ("src.claude/skills/lead/SKILL.md", "dispatch:subagent_type-lead"): 1,
            ("src.codex/AGENTS.codex.md", "dispatch:lead-spawned"): 1,
        }
    )
    assert Counter(name for _path, name, _polarity in occurrences) == Counter(
        {
            "dispatch:subagent_type-lead": 5,
            "dispatch:verb-lead": 2,
            "dispatch:lead-spawned": 2,
        }
    )
    assert all(polarity is _DispatchPolarity.REFUSED for _path, _name, polarity in occurrences)


def test_english_only_language_boundary():
    russian_lines = (
        "Запусти `$lead` как подагента",
        "Не запускай `$lead` как подагента",
    )
    discovered = [
        (line, [name for name, pattern in FORBIDDEN if name.startswith("dispatch:") and pattern.search(line)])
        for line in russian_lines
    ]
    assert discovered == [(line, []) for line in russian_lines]  # OUT_OF_CONTRACT, not polarity PASS.
    assert (
        _line_verdict("обёртка запрещает `subagent_type: lead` как маршрут")
        == "dispatch:subagent_type-lead"
    )


def test_guard_allows_known_fine_forms():
    false_positives = [(s, _line_verdict(s)) for s in _KNOWN_FINE_FORMS if _line_verdict(s) is not None]
    assert not false_positives, f"guard false-flagged legitimate FINE form(s): {false_positives}"
