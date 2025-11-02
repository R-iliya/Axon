# axon/lexer.py
import re
from dataclasses import dataclass
from typing import List, Iterator, Tuple, Optional

TOKEN_SPEC: List[Tuple[str, str]] = [
    ("NUMBER", r"\d+(\.\d+)?"),
    ("IDENT", r"[A-Za-z_][A-Za-z0-9_]*"),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("PLUS", r"\+"),
    ("MINUS", r"-"),
    ("TIMES", r"\*"),
    ("DIV", r"/"),
    ("EQ", r"="),
    ("SEMICOL", r";"),
    ("SKIP", r"[ \t]+"),
    ("NEWLINE", r"\n"),
    ("COMMENT", r"//[^\n]*"),
]

MASTER_RE = re.compile("|".join(f"(?P<{name}>{pat})" for name, pat in TOKEN_SPEC))


@dataclass
class Token:
    type: str
    value: str
    pos: int
    lineno: int
    col: int

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, line={self.lineno}, col={self.col})"


def tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    lineno = 1
    line_start = 0
    for m in MASTER_RE.finditer(text):
        typ = m.lastgroup
        val = m.group(typ)
        pos = m.start()
        col = pos - line_start + 1
        if typ == "NEWLINE":
            lineno += 1
            line_start = m.end()
            continue
        if typ == "SKIP" or typ == "COMMENT":
            continue
        tokens.append(Token(typ, val, pos, lineno, col))
    tokens.append(Token("EOF", "", len(text), lineno, 1))
    return tokens


if __name__ == "__main__":
    import sys

    s = open(sys.argv[1]).read() if len(sys.argv) > 1 else "print(1+2*3);"
    for t in tokenize(s):
        print(t)
