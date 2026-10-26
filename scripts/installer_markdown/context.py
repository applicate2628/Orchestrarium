"""Lift committed stock Markdown code nodes to original LF string offsets.

The pinned paragraph/heading extractors preserve backticks in source order.
Ordinal backtick correspondence therefore lifts parser-chosen endpoints without
searching normalized token text or implementing Markdown extraction grammar.
Image labels transport an exact parent slice; link parsing retains its source.
"""
from dataclasses import dataclass, field

from markdown_it import MarkdownIt
from markdown_it.rules_core import inline as core_inline
from markdown_it.rules_inline import image, link
from markdown_it.rules_inline.backticks import backtick


class ContextProvenanceError(RuntimeError):
    """The pinned parser's source-origin contract was not acquired."""


def _require(condition: bool, label: str) -> None:
    if not condition:
        raise ContextProvenanceError("E_INSTALLER_MARKDOWN_ORIGIN: " + label)


@dataclass(frozen=True)
class _Root:
    text: str
    delimiters: dict[int, int]


@dataclass(frozen=True)
class _Origin:
    root: _Root
    base: int
    text: str


@dataclass
class _Parent:
    kind: str
    origin: _Origin
    child_start: int
    child_tokens: list | None = None
    spans: list[tuple[int, int]] = field(default_factory=list)


class _CodeContext:
    def __init__(self, source: str):
        self.source = source
        self.normalized = source.replace("\x00", "\ufffd")
        self.bounds = [0] + [i + 1 for i, char in enumerate(source) if char == "\n"]
        if self.bounds[-1] != len(source):
            self.bounds.append(len(source))
        self.inline_origins: dict[int, tuple[list, _Origin]] = {}
        self.parents: list[_Parent] = []
        self.spans: list[tuple[int, int]] = []
        # Every further content-bearing stock nesting level consumes source
        # syntax. This avoids the default20 cutoff, not Python resource limits
        # or the separately documented stock link-destination grammar bound.
        self.parser = MarkdownIt("commonmark", {"maxNesting": len(source) + 1})
        self._wrap_rules()

    def _wrap_rules(self) -> None:
        # Stock block parsing and all its alternate chains remain untouched.
        # Acquire committed output at the stock core's inline boundary instead.
        self.parser.core.ruler.at("inline", self._inline_roots)
        self.parser.inline.ruler.at("backticks", self._backticks)
        self.parser.inline.ruler.at("image", self._image)
        self.parser.inline.ruler.at("link", self._link)

    def _inline_roots(self, state) -> None:
        _require(state.src == self.normalized, "normalized-source-identity")
        previous_end = 0
        committed = []
        for token in state.tokens:
            if token.type != "inline":
                continue
            _require(token.map is not None, "root-line-map")
            line_range = tuple(token.map)
            begin, end = self._line_span(line_range)
            _require(previous_end <= begin, "overlapping-root-ranges")
            previous_end = end
            original_ticks = [i for i in range(begin, end) if self.source[i] == "`"]
            inline_ticks = [i for i, char in enumerate(token.content) if char == "`"]
            _require(len(original_ticks) == len(inline_ticks), "delimiter-conservation")
            _require(token.children is not None, "root-token-list")
            root = _Root(token.content, dict(zip(inline_ticks, original_ticks)))
            self.inline_origins[id(token.children)] = (token.children, _Origin(root, 0, token.content))
            committed.append((token, token.content, line_range, token.children))
        core_inline(state)
        for token, content, line_range, children in committed:
            _require(token.content == content and tuple(token.map) == line_range
                     and token.children is children, "root-identity")
        _require(not self.parents, "unsettled-parent")

    def _line_span(self, line_range) -> tuple[int, int]:
        _require(line_range is not None and len(line_range) == 2, "missing-line-range")
        start, end = line_range
        _require(0 <= start <= end < len(self.bounds), "line-range")
        return self.bounds[start], self.bounds[end]

    def _origin(self, state) -> _Origin:
        acquired = self.inline_origins.get(id(state.tokens))
        if acquired is not None:
            tokens, origin = acquired
            _require(tokens is state.tokens and origin.text == state.src, "inline-identity")
            return origin
        _require(bool(self.parents), "fresh-inline-without-parent")
        parent = self.parents[-1]
        _require(parent.kind == "image", "unexpected-fresh-inline")
        origin, start = parent.origin, parent.child_start
        _require(origin.text[start:start + len(state.src)] == state.src, "image-substring-origin")
        _require(parent.child_tokens is None or parent.child_tokens is state.tokens, "multiple-image-subparses")
        parent.child_tokens = state.tokens
        child = _Origin(origin.root, origin.base + start, state.src)
        _require(child.root.text[child.base:child.base + len(state.src)] == state.src, "composed-child-origin")
        self.inline_origins[id(state.tokens)] = (state.tokens, child)
        return child

    def _publish(self, spans: list[tuple[int, int]]) -> None:
        if self.parents:
            self.parents[-1].spans.extend(spans)
        else:
            self.spans.extend(spans)

    def _backticks(self, state, silent):
        count, start = len(state.tokens), state.pos
        result = backtick(state, silent)
        emitted = [token for token in state.tokens[count:] if token.type == "code_inline"]
        _require(not silent or not emitted, "silent-code-emission")
        _require(len(emitted) <= 1, "multiple-code-emissions")
        if emitted:
            _require(result and not silent, "uncommitted-code")
            origin = self._origin(state)
            begin, end = origin.base + start, origin.base + state.pos
            lookup = origin.root.delimiters
            _require(begin in lookup and end - 1 in lookup, "code-endpoint-origin")
            self._publish([(lookup[begin], lookup[end - 1] + 1)])
        return result

    def _parent_rule(self, kind, original, state, silent):
        if silent:
            return original(state, silent)
        origin = self._origin(state)
        start, count, source, tokens = state.pos, len(state.tokens), state.src, state.tokens
        parent = _Parent(kind, origin, start + 2 if kind == "image" else 0)
        self.parents.append(parent)
        try:
            result = original(state, silent)
        finally:
            _require(self.parents[-1] is parent, "parent-stack-order")
            self.parents.pop()
        _require(state.src == source and state.tokens is tokens, "parent-source-identity")
        added = state.tokens[count:]
        if not result:
            _require(not parent.spans, "failed-parent-published-code")
            return result
        if kind == "image":
            images = [token for token in added if token.type == "image"]
            _require(len(images) == 1, "image-commit-token")
            node = images[0]
            _require(source[parent.child_start:parent.child_start + len(node.content)] == node.content,
                     "committed-image-slice")
            _require(parent.child_tokens is None or node.children is parent.child_tokens, "image-child-identity")
        else:
            _require(any(token.type == "link_open" for token in added)
                     and any(token.type == "link_close" for token in added), "link-commit-tokens")
        self._publish(parent.spans)
        return result

    def _image(self, state, silent):
        return self._parent_rule("image", image, state, silent)

    def _link(self, state, silent):
        return self._parent_rule("link", link, state, silent)

    def run(self) -> tuple[str, list[tuple[int, int]]]:
        tokens = self.parser.parse(self.source)
        for token in tokens:
            if token.type in ("fence", "code_block"):
                self.spans.append(self._line_span(token.map))
        spans = sorted(self.spans)
        _require(all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), "overlapping-code-spans")
        visible = list(self.source)
        for begin, end in spans:
            for index in range(begin, end):
                if visible[index] != "\n":
                    visible[index] = " "
        return "".join(visible), spans


def document_context(source: str) -> tuple[str, list[tuple[int, int]]]:
    """Return a same-offset projection and committed code spans in LF input."""
    return _CodeContext(source).run()
