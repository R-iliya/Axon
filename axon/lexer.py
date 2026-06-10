# axon/lexer.py
"""
Lexer for the Axon language.
Converts raw source text into a flat list of Token objects.

Supported tokens:
  Literals   : NUMBER, STRING
  Keywords   : let, if, else, elif, while, for, to, fn, return,
               break, continue, cls, true, false
  Operators  : + - * / % == != < > <= >= = and or not
  Delimiters : ( ) { } [ ] , ; :
  Other      : IDENT, EOF

Comments    : // … (line comments, stripped before tokenising)
"""

import re
from dataclasses import dataclass
from typing import List


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

# All keyword strings — recognised as KEYWORD tokens, not IDENT.
KEYWORDS = frozenset({
    "let", "if", "else", "elif", "while", "for", "to",
    "fn", "return", "break", "continue", "cls",
    "true", "false", "and", "or", "not",
})


@dataclass(frozen=True)
class Token:
    type: str       # e.g. 'NUMBER', 'STRING', 'IDENT', 'KEYWORD', 'OP', ...
    value: object   # str | int | float
    line: int
    col: int

    def __repr__(self) -> str:
        return f"Token({self.type}, {self.value!r}, {self.line}:{self.col})"


# ---------------------------------------------------------------------------
# Token spec  (order matters — earlier patterns win)
# ---------------------------------------------------------------------------

_TOKEN_SPEC = [
    # -- Literals --
    ("NUMBER",     r"\d+\.\d*|\d+"),           # int or float
    ("STRING",     r'"(?:[^"\\]|\\.)*"'),       # "…" with escape sequences

    # -- Multi-char operators (must come before single-char) --
    ("OP",         r"==|!=|<=|>=|<|>|\+|-|\*|/|%|="),

    # -- Delimiters --
    ("LPAREN",     r"\("),
    ("RPAREN",     r"\)"),
    ("LBRACE",     r"\{"),
    ("RBRACE",     r"\}"),
    ("LBRACKET",   r"\["),
    ("RBRACKET",   r"\]"),
    ("COMMA",      r","),
    ("SEMICOLON",  r";"),
    ("COLON",      r":"),

    # -- Identifiers / keywords (checked after everything else) --
    ("IDENT",      r"[A-Za-z_][A-Za-z0-9_]*"),

    # -- Whitespace (skip) --
    ("SKIP",       r"[ \t\r]+"),
    ("NEWLINE",    r"\n"),

    # -- Catch-all for unexpected characters --
    ("MISMATCH",   r"."),
]

_TOKEN_RE = re.compile(
    "|".join(f"(?P<{name}>{pattern})" for name, pattern in _TOKEN_SPEC)
)


# ---------------------------------------------------------------------------
# LexError
# ---------------------------------------------------------------------------

class LexError(Exception):
    def __init__(self, char: str, line: int, col: int):
        super().__init__(f"Unexpected character {char!r} at line {line}, col {col}")
        self.char = char
        self.line = line
        self.col = col


# ---------------------------------------------------------------------------
# Pre-processing: strip line comments
# ---------------------------------------------------------------------------

def _strip_comments(source: str) -> str:
    """Remove // … comments while preserving line numbers."""
    result = []
    for line in source.splitlines(keepends=True):
        # Find // that is NOT inside a string literal.
        # Simple approach: scan char by char for the first // outside quotes.
        in_str = False
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '"' and not in_str:
                in_str = True
            elif ch == '"' and in_str:
                in_str = False
            elif ch == '\\' and in_str:
                i += 1          # skip escaped char
            elif ch == '/' and not in_str and i + 1 < len(line) and line[i + 1] == '/':
                # rest of line is a comment — keep the newline if present
                eol = '\n' if line.endswith('\n') else ''
                result.append(line[:i] + eol)
                break
            i += 1
        else:
            result.append(line)
    return "".join(result)


# ---------------------------------------------------------------------------
# _cook_string  — turn a raw "…" token value into a Python str
# ---------------------------------------------------------------------------

_ESCAPE_MAP = {
    'n':  '\n',
    't':  '\t',
    'r':  '\r',
    '\\': '\\',
    '"':  '"',
    '0':  '\0',
}

def _cook_string(raw: str) -> str:
    """Convert a raw quoted string literal (including surrounding quotes) to str."""
    result = []
    s = raw[1:-1]   # strip surrounding double-quotes
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == '\\' and i + 1 < len(s):
            nxt = s[i + 1]
            result.append(_ESCAPE_MAP.get(nxt, nxt))
            i += 2
        else:
            result.append(ch)
            i += 1
    return "".join(result)


# ---------------------------------------------------------------------------
# tokenize
# ---------------------------------------------------------------------------

def tokenize(source: str) -> List[Token]:
    """
    Lex *source* and return a list of Token objects.
    Raises LexError on unexpected characters.
    Does NOT include a final EOF token — callers that need one can append it.
    """
    source = _strip_comments(source)

    tokens: List[Token] = []
    line_num = 1
    line_start = 0

    for mo in _TOKEN_RE.finditer(source):
        kind  = mo.lastgroup
        raw   = mo.group()
        col   = mo.start() - line_start + 1

        if kind == "SKIP":
            continue

        elif kind == "NEWLINE":
            line_num += 1
            line_start = mo.end()
            continue

        elif kind == "MISMATCH":
            raise LexError(raw, line_num, col)

        elif kind == "NUMBER":
            value = float(raw) if '.' in raw else int(raw)
            tokens.append(Token("NUMBER", value, line_num, col))

        elif kind == "STRING":
            tokens.append(Token("STRING", _cook_string(raw), line_num, col))

        elif kind == "IDENT":
            if raw in KEYWORDS:
                tokens.append(Token("KEYWORD", raw, line_num, col))
            else:
                tokens.append(Token("IDENT", raw, line_num, col))

        else:
            # OP and all delimiter types pass through as-is
            tokens.append(Token(kind, raw, line_num, col))

    return tokens