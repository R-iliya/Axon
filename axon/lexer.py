# axon/lexer.py
import re
from dataclasses import dataclass
from typing import List, Iterator, Tuple, Optional

TOKEN_SPEC = [
    ('NUMBER',   r'\d+(\.\d*)?'),
    ('STRING',   r'"([^"\\]|\\.)*"'),
    ('IDENT',    r'[A-Za-z_][A-Za-z0-9_]*'),
    ('LPAREN',   r'\('),
    ('RPAREN',   r'\)'),
    ('LBRACE',   r'\{'),
    ('RBRACE',   r'\}'),
    ('SEMICOLON',r';'),
    ('COMMA',    r','),
    ('EQ',       r'='),
    ('OP',       r'[+\-*/]'),
    ('SKIP',     r'[ \t]+'),
    ('NEWLINE',  r'\n'),
    ('MISMATCH', r'.'),
]

TOKEN_RE = re.compile('|'.join(f'(?P<{name}>{pattern})' for name, pattern in TOKEN_SPEC))

class Token:
    def __init__(self, type_, value, line, col):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col
    def __repr__(self):
        return f'Token({self.type}, {self.value})'

def tokenize(code):
    line_num = 1
    line_start = 0
    tokens = []
    for mo in TOKEN_RE.finditer(code):
        kind = mo.lastgroup
        value = mo.group()
        col = mo.start() - line_start + 1
        if kind == 'NUMBER':
            value = float(value) if '.' in value else int(value)
        elif kind == 'STRING':
            value = bytes(value[1:-1], "utf-8").decode("unicode_escape")
        elif kind == 'NEWLINE':
            line_num += 1
            line_start = mo.end()
            continue
        elif kind == 'SKIP':
            continue
        elif kind == 'MISMATCH':
            raise SyntaxError(f'Unexpected {value!r} at line {line_num}')
        tokens.append(Token(kind, value, line_num, col))
    return tokens
