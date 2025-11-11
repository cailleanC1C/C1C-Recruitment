"""Parser for onboarding rule directives and expressions."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterator, List, Sequence

__all__ = [
    "RuleParseError",
    "Expression",
    "Literal",
    "Identifier",
    "ListLiteral",
    "UnaryExpression",
    "BinaryExpression",
    "FunctionCall",
    "VisibilityDirective",
    "NavDirective",
    "parse_visibility_rules",
    "parse_nav_rules",
]


class RuleParseError(ValueError):
    """Raised when rule text fails to parse."""


@dataclass(frozen=True)
class Expression:
    """Base node for expression AST."""


@dataclass(frozen=True)
class Literal(Expression):
    value: object


@dataclass(frozen=True)
class Identifier(Expression):
    name: str


@dataclass(frozen=True)
class ListLiteral(Expression):
    items: tuple[Expression, ...]


@dataclass(frozen=True)
class UnaryExpression(Expression):
    op: str
    operand: Expression


@dataclass(frozen=True)
class BinaryExpression(Expression):
    op: str
    left: Expression
    right: Expression


@dataclass(frozen=True)
class FunctionCall(Expression):
    name: str
    args: tuple[Expression, ...]


@dataclass(frozen=True)
class VisibilityDirective:
    kind: str
    expression: Expression
    raw: str


@dataclass(frozen=True)
class NavDirective:
    target: str
    expression: Expression
    raw: str


_TOKEN_REGEX = re.compile(
    r"\s*("
    r"(?P<NUMBER>-?\d+(?:\.\d+)?)"
    r"|(?P<STRING>'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")"
    r"|(?P<OP><=|>=|!=|=|<|>|\(|\)|\[|\]|,)"
    r"|(?P<NAME>[A-Za-z_][A-Za-z0-9_]*)"
    r")"
)

_KEYWORDS = {"and", "or", "not", "in"}


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str


class _TokenStream:
    def __init__(self, expression: str) -> None:
        self._tokens: List[_Token] = []
        for match in _TOKEN_REGEX.finditer(expression):
            if match.group("NUMBER") is not None:
                self._tokens.append(_Token("NUMBER", match.group("NUMBER")))
                continue
            if match.group("STRING") is not None:
                self._tokens.append(_Token("STRING", match.group("STRING")))
                continue
            if match.group("OP") is not None:
                symbol = match.group("OP")
                mapping = {
                    "(": "LPAREN",
                    ")": "RPAREN",
                    "[": "LBRACKET",
                    "]": "RBRACKET",
                    ",": "COMMA",
                }
                self._tokens.append(_Token(mapping.get(symbol, symbol), symbol))
                continue
            name = match.group("NAME")
            if name:
                lowered = name.lower()
                if lowered in _KEYWORDS:
                    self._tokens.append(_Token(lowered.upper(), lowered))
                else:
                    self._tokens.append(_Token("NAME", name))
        self._index = 0

    def peek(self) -> _Token | None:
        if self._index < len(self._tokens):
            return self._tokens[self._index]
        return None

    def advance(self) -> _Token | None:
        token = self.peek()
        if token is not None:
            self._index += 1
        return token

    def expect(self, kind: str) -> _Token:
        token = self.advance()
        if token is None or token.kind != kind:
            raise RuleParseError(f"expected {kind}")
        return token

    def match(self, kind: str) -> bool:
        token = self.peek()
        if token is not None and token.kind == kind:
            self._index += 1
            return True
        return False


def _parse_expression(stream: _TokenStream) -> Expression:
    return _parse_or(stream)


def _parse_or(stream: _TokenStream) -> Expression:
    left = _parse_and(stream)
    while stream.match("OR"):
        right = _parse_and(stream)
        left = BinaryExpression("or", left, right)
    return left


def _parse_and(stream: _TokenStream) -> Expression:
    left = _parse_not(stream)
    while stream.match("AND"):
        right = _parse_not(stream)
        left = BinaryExpression("and", left, right)
    return left


def _parse_not(stream: _TokenStream) -> Expression:
    if stream.match("NOT"):
        operand = _parse_not(stream)
        return UnaryExpression("not", operand)
    return _parse_comparison(stream)


def _parse_comparison(stream: _TokenStream) -> Expression:
    left = _parse_term(stream)
    token = stream.peek()
    if token is None:
        return left
    if token.kind in {"=", "!=", "<", "<=", ">", ">="}:
        stream.advance()
        right = _parse_term(stream)
        return BinaryExpression(token.kind, left, right)
    if token.kind == "IN":
        stream.advance()
        right = _parse_list_literal(stream)
        return BinaryExpression("in", left, right)
    return left


def _parse_list_literal(stream: _TokenStream) -> Expression:
    stream.expect("LBRACKET")
    items: List[Expression] = []
    if not stream.match("RBRACKET"):
        while True:
            element = _parse_expression(stream)
            if isinstance(element, Identifier):
                element = Literal(element.name)
            items.append(element)
            if stream.match("COMMA"):
                continue
            stream.expect("RBRACKET")
            break
    return ListLiteral(tuple(items))


def _parse_term(stream: _TokenStream) -> Expression:
    token = stream.peek()
    if token is None:
        raise RuleParseError("unexpected end of expression")
    if token.kind == "LPAREN":
        stream.advance()
        expr = _parse_expression(stream)
        stream.expect("RPAREN")
        return expr
    if token.kind == "NUMBER":
        stream.advance()
        return Literal(token.value)
    if token.kind == "STRING":
        stream.advance()
        value = token.value
        return Literal(_unquote(value))
    if token.kind == "NAME":
        stream.advance()
        name = token.value
        lowered = name.lower()
        if lowered in {"true", "false"}:
            return Literal(lowered == "true")
        if stream.match("LPAREN"):
            args: List[Expression] = []
            if not stream.match("RPAREN"):
                while True:
                    args.append(_parse_expression(stream))
                    if stream.match("COMMA"):
                        continue
                    stream.expect("RPAREN")
                    break
            return FunctionCall(name, tuple(args))
        return Identifier(name)
    raise RuleParseError(f"unexpected token: {token.value}")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        body = value[1:-1]
        return bytes(body, "utf-8").decode("unicode_escape")
    return value


def _split_directives(text: str) -> Iterator[str]:
    for raw_line in text.splitlines():
        clause = raw_line.strip()
        if clause:
            yield clause


_VISIBILITY_PATTERN = re.compile(
    r"^(?P<kind>skip|optional|require|show)_if\((?P<body>.+)\)$",
    re.IGNORECASE,
)


def parse_visibility_rules(text: str | None, *, qid: str) -> list[VisibilityDirective]:
    directives: list[VisibilityDirective] = []
    if not text:
        return directives
    for clause in _split_directives(text):
        match = _VISIBILITY_PATTERN.match(clause)
        if not match:
            raise RuleParseError(f"unsupported visibility directive: {clause}")
        kind = match.group("kind").lower()
        body = match.group("body").strip()
        stream = _TokenStream(body)
        expression = _parse_expression(stream)
        if stream.peek() is not None:
            raise RuleParseError("unexpected trailing tokens")
        directives.append(VisibilityDirective(kind=kind, expression=expression, raw=clause))
    return directives


def _split_nav_body(body: str) -> tuple[str, str | None]:
    depth = 0
    parts: list[str] = []
    current: list[str] = []
    for char in body:
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        if char in "([":
            depth += 1
        elif char in ")]":
            depth = max(0, depth - 1)
        current.append(char)
    if current:
        parts.append("".join(current).strip())
    expr = parts[0] if parts else ""
    target = None
    for fragment in parts[1:]:
        lowered = fragment.lower()
        if not lowered.startswith("target"):
            continue
        before, sep, after = fragment.partition("=")
        if sep:
            target = after.strip()
            break
    return expr, target


_NAV_PATTERN = re.compile(r"^goto_if\((?P<body>.+)\)$", re.IGNORECASE)


def parse_nav_rules(text: str | None, *, qid: str) -> list[NavDirective]:
    directives: list[NavDirective] = []
    if not text:
        return directives
    for clause in _split_directives(text):
        match = _NAV_PATTERN.match(clause)
        if not match:
            raise RuleParseError(f"unsupported navigation directive: {clause}")
        body = match.group("body").strip()
        expr_text, target_fragment = _split_nav_body(body)
        if not target_fragment:
            raise RuleParseError("goto_if directive missing target")
        target = _parse_target(target_fragment)
        stream = _TokenStream(expr_text)
        expression = _parse_expression(stream)
        if stream.peek() is not None:
            raise RuleParseError("unexpected trailing tokens")
        directives.append(NavDirective(target=target, expression=expression, raw=clause))
    return directives


_TARGET_PATTERN = re.compile(r"^\"?(?P<target>[A-Za-z0-9_]+)\"?$")


def _parse_target(fragment: str) -> str:
    text = fragment.strip()
    if text.startswith(('"', "'")) and text.endswith(('"', "'")) and len(text) >= 2:
        text = text[1:-1]
    match = _TARGET_PATTERN.match(text)
    if not match:
        raise RuleParseError(f"invalid navigation target: {fragment}")
    return match.group("target")
