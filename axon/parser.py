# axon/parser.py
"""
Recursive-descent parser for the Axon language.

Consumes a flat list of Token objects (from axon.lexer) and produces
a tuple of AST nodes (from axon.nodes) representing the program.

Grammar (informal)
------------------
program      → stmt* EOF

stmt         → let_stmt
             | assign_stmt
             | print_stmt
             | clear_stmt
             | if_stmt
             | while_stmt
             | for_stmt
             | fn_stmt
             | return_stmt
             | break_stmt
             | continue_stmt
             | expr_stmt

let_stmt     → 'let' IDENT '=' expr ';'
assign_stmt  → IDENT '=' expr ';'          (only when next token is '=')
print_stmt   → 'print' '(' expr ')' ';'
clear_stmt   → 'cls' ';'
if_stmt      → 'if' expr block
               ('elif' expr block)*
               ('else' block)?
while_stmt   → 'while' expr block
for_stmt     → 'for' IDENT '=' expr 'to' expr block
fn_stmt      → 'fn' IDENT '(' params ')' block
return_stmt  → 'return' expr? ';'
break_stmt   → 'break' ';'
continue_stmt→ 'continue' ';'
expr_stmt    → expr ';'

block        → '{' stmt* '}'
params       → (IDENT (',' IDENT)*)?

expr         → logic_or
logic_or     → logic_and ('or' logic_and)*
logic_and    → comparison ('and' comparison)*
comparison   → term (('=='|'!='|'<'|'>'|'<='|'>=') term)*
term         → factor (('+' | '-') factor)*
factor       → unary (('*' | '/' | '%') unary)*
unary        → ('-' | 'not') unary | primary
primary      → NUMBER | STRING | 'true' | 'false'
             | IDENT ( '(' args ')' | ('[' expr ']')* )?
             | '(' expr ')'
             | '[' args ']'
             | '{' dict_entries '}'

args         → (expr (',' expr)*)?
dict_entries → (expr ':' expr (',' expr ':' expr)*)?
"""

from __future__ import annotations
from typing import List, Tuple, Optional
from axon.lexer import Token, tokenize
from axon.nodes import (
    Node,
    NumberLit, StringLit, BoolLit, Var,
    BinOp, UnaryOp, ListLit, DictLit, Index, Call,
    Let, Assign, Print, Clear,
    If, While, For,
    Break, Continue, Return,
    FnDef, ExprStmt,
)


# ---------------------------------------------------------------------------
# ParseError
# ---------------------------------------------------------------------------

class ParseError(Exception):
    def __init__(self, msg: str, line: int = 0, col: int = 0):
        location = f" (line {line}, col {col})" if line else ""
        super().__init__(f"{msg}{location}")
        self.line = line
        self.col  = col


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class Parser:
    def __init__(self, tokens: List[Token]):
        self._tokens = tokens
        self._pos    = 0

    # ------------------------------------------------------------------
    # Token navigation helpers
    # ------------------------------------------------------------------

    def _current(self) -> Optional[Token]:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _peek(self, offset: int = 1) -> Optional[Token]:
        idx = self._pos + offset
        if idx < len(self._tokens):
            return self._tokens[idx]
        return None

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _at_end(self) -> bool:
        return self._pos >= len(self._tokens)

    # ------------------------------------------------------------------
    # Expectation helpers
    # ------------------------------------------------------------------

    def _expect(self, ttype: str, tvalue: object = None) -> Token:
        """
        Consume and return the current token if it matches type (and
        optionally value).  Raises ParseError otherwise.
        """
        tok = self._current()
        if tok is None:
            raise ParseError(
                f"Expected {ttype!r}"
                + (f" '{tvalue}'" if tvalue is not None else "")
                + " but reached end of input"
            )
        if tok.type != ttype:
            raise ParseError(
                f"Expected {ttype!r}"
                + (f" '{tvalue}'" if tvalue is not None else "")
                + f" but got {tok.type!r} '{tok.value}'",
                tok.line, tok.col,
            )
        if tvalue is not None and tok.value != tvalue:
            raise ParseError(
                f"Expected '{tvalue}' but got '{tok.value}'",
                tok.line, tok.col,
            )
        return self._advance()

    def _expect_kw(self, kw: str) -> Token:
        return self._expect("KEYWORD", kw)

    def _expect_op(self, op: str) -> Token:
        return self._expect("OP", op)

    def _expect_semi(self) -> Token:
        tok = self._current()
        if tok is None or tok.type != "SEMICOLON":
            # Give a helpful location — point at whatever we're sitting on
            line = tok.line if tok else 0
            col  = tok.col  if tok else 0
            raise ParseError("Expected ';' after statement", line, col)
        return self._advance()

    def _match_kw(self, *kws: str) -> bool:
        tok = self._current()
        return tok is not None and tok.type == "KEYWORD" and tok.value in kws

    def _match_op(self, *ops: str) -> bool:
        tok = self._current()
        return tok is not None and tok.type == "OP" and tok.value in ops

    def _match_type(self, ttype: str) -> bool:
        tok = self._current()
        return tok is not None and tok.type == ttype

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def parse(self) -> Tuple[Node, ...]:
        stmts = []
        while not self._at_end():
            stmts.append(self._parse_stmt())
        return tuple(stmts)

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def _parse_stmt(self) -> Node:
        tok = self._current()
        if tok is None:
            raise ParseError("Unexpected end of input")

        # -- keyword-led statements --
        if tok.type == "KEYWORD":
            if tok.value == "let":      return self._parse_let()
            if tok.value == "print":    return self._parse_print()
            if tok.value == "cls":      return self._parse_clear()
            if tok.value == "if":       return self._parse_if()
            if tok.value == "while":    return self._parse_while()
            if tok.value == "for":      return self._parse_for()
            if tok.value == "fn":       return self._parse_fn()
            if tok.value == "return":   return self._parse_return()
            if tok.value == "break":    return self._parse_break()
            if tok.value == "continue": return self._parse_continue()

        # -- bare assignment:  IDENT '=' expr ';'  --
        if (tok.type == "IDENT"
                and self._peek() is not None
                and self._peek().type == "OP"
                and self._peek().value == "="):
            return self._parse_assign()

        # -- everything else is an expression statement --
        return self._parse_expr_stmt()

    def _parse_let(self) -> Let:
        tok  = self._expect_kw("let")
        name = self._expect("IDENT")
        self._expect_op("=")
        expr = self._parse_expr()
        self._expect_semi()
        return Let(tok.line, tok.col, name.value, expr)

    def _parse_assign(self) -> Assign:
        name = self._expect("IDENT")
        self._expect_op("=")
        expr = self._parse_expr()
        self._expect_semi()
        return Assign(name.line, name.col, name.value, expr)

    def _parse_print(self) -> Print:
        tok = self._expect_kw("print")
        self._expect("LPAREN")
        expr = self._parse_expr()
        self._expect("RPAREN")
        self._expect_semi()
        return Print(tok.line, tok.col, expr)

    def _parse_clear(self) -> Clear:
        tok = self._expect_kw("cls")
        self._expect_semi()
        return Clear(tok.line, tok.col)

    def _parse_break(self) -> Break:
        tok = self._expect_kw("break")
        self._expect_semi()
        return Break(tok.line, tok.col)

    def _parse_continue(self) -> Continue:
        tok = self._expect_kw("continue")
        self._expect_semi()
        return Continue(tok.line, tok.col)

    def _parse_return(self) -> Return:
        tok = self._expect_kw("return")
        # bare return  →  return;
        if self._match_type("SEMICOLON"):
            self._advance()
            return Return(tok.line, tok.col, None)
        expr = self._parse_expr()
        self._expect_semi()
        return Return(tok.line, tok.col, expr)

    def _parse_if(self) -> If:
        tok = self._expect_kw("if")
        branches = []

        # first 'if' branch
        cond = self._parse_expr()
        body = self._parse_block()
        branches.append((cond, body))

        # zero or more 'elif' branches
        while self._match_kw("elif"):
            self._advance()
            cond = self._parse_expr()
            body = self._parse_block()
            branches.append((cond, body))

        # optional 'else'
        else_body: Tuple[Node, ...] = ()
        if self._match_kw("else"):
            self._advance()
            else_body = self._parse_block()

        return If(tok.line, tok.col, tuple(branches), else_body)

    def _parse_while(self) -> While:
        tok  = self._expect_kw("while")
        cond = self._parse_expr()
        body = self._parse_block()
        return While(tok.line, tok.col, cond, body)

    def _parse_for(self) -> For:
        tok  = self._expect_kw("for")
        name = self._expect("IDENT")
        self._expect_op("=")
        start = self._parse_expr()
        self._expect_kw("to")
        end  = self._parse_expr()
        body = self._parse_block()
        return For(tok.line, tok.col, name.value, start, end, body)

    def _parse_fn(self) -> FnDef:
        tok  = self._expect_kw("fn")
        name = self._expect("IDENT")
        self._expect("LPAREN")
        params = self._parse_params()
        self._expect("RPAREN")
        body = self._parse_block()
        return FnDef(tok.line, tok.col, name.value, params, body)

    def _parse_expr_stmt(self) -> ExprStmt:
        tok  = self._current()
        expr = self._parse_expr()
        self._expect_semi()
        return ExprStmt(tok.line, tok.col, expr)

    # ------------------------------------------------------------------
    # Block  { stmt* }
    # ------------------------------------------------------------------

    def _parse_block(self) -> Tuple[Node, ...]:
        self._expect("LBRACE")
        stmts = []
        while not self._at_end() and not self._match_type("RBRACE"):
            stmts.append(self._parse_stmt())
        self._expect("RBRACE")
        return tuple(stmts)

    # ------------------------------------------------------------------
    # Parameter list  (IDENT (',' IDENT)*)
    # ------------------------------------------------------------------

    def _parse_params(self) -> Tuple[str, ...]:
        params = []
        if self._match_type("IDENT"):
            params.append(self._advance().value)
            while self._match_type("COMMA"):
                self._advance()
                params.append(self._expect("IDENT").value)
        return tuple(params)

    # ------------------------------------------------------------------
    # Expressions  (precedence climbing via recursive descent)
    # ------------------------------------------------------------------

    def _parse_expr(self) -> Node:
        return self._parse_logic_or()

    def _parse_logic_or(self) -> Node:
        left = self._parse_logic_and()
        while self._match_kw("or"):
            tok = self._advance()
            right = self._parse_logic_and()
            left = BinOp(tok.line, tok.col, left, "or", right)
        return left

    def _parse_logic_and(self) -> Node:
        left = self._parse_comparison()
        while self._match_kw("and"):
            tok = self._advance()
            right = self._parse_comparison()
            left = BinOp(tok.line, tok.col, left, "and", right)
        return left

    def _parse_comparison(self) -> Node:
        left = self._parse_term()
        while self._match_op("==", "!=", "<", ">", "<=", ">="):
            tok = self._advance()
            right = self._parse_term()
            left = BinOp(tok.line, tok.col, left, tok.value, right)
        return left

    def _parse_term(self) -> Node:
        left = self._parse_factor()
        while self._match_op("+", "-"):
            tok = self._advance()
            right = self._parse_factor()
            left = BinOp(tok.line, tok.col, left, tok.value, right)
        return left

    def _parse_factor(self) -> Node:
        left = self._parse_unary()
        while self._match_op("*", "/", "%"):
            tok = self._advance()
            right = self._parse_unary()
            left = BinOp(tok.line, tok.col, left, tok.value, right)
        return left

    def _parse_unary(self) -> Node:
        if self._match_op("-"):
            tok  = self._advance()
            expr = self._parse_unary()
            return UnaryOp(tok.line, tok.col, "-", expr)
        if self._match_kw("not"):
            tok  = self._advance()
            expr = self._parse_unary()
            return UnaryOp(tok.line, tok.col, "not", expr)
        return self._parse_primary()

    def _parse_primary(self) -> Node:
        tok = self._current()
        if tok is None:
            raise ParseError("Unexpected end of input while parsing expression")

        # -- number literal --
        if tok.type == "NUMBER":
            self._advance()
            return NumberLit(tok.line, tok.col, tok.value)

        # -- string literal --
        if tok.type == "STRING":
            self._advance()
            return StringLit(tok.line, tok.col, tok.value)

        # -- boolean literals --
        if tok.type == "KEYWORD" and tok.value == "true":
            self._advance()
            return BoolLit(tok.line, tok.col, True)
        if tok.type == "KEYWORD" and tok.value == "false":
            self._advance()
            return BoolLit(tok.line, tok.col, False)

        # -- identifier: variable, function call, or index --
        if tok.type == "IDENT":
            self._advance()
            # function call: foo(...)
            if self._match_type("LPAREN"):
                self._advance()
                args = self._parse_args()
                self._expect("RPAREN")
                node: Node = Call(tok.line, tok.col, tok.value, args)
            else:
                node = Var(tok.line, tok.col, tok.value)

            # chained indexing: expr[idx][idx]...
            while self._match_type("LBRACKET"):
                self._advance()
                idx = self._parse_expr()
                rb  = self._expect("RBRACKET")
                node = Index(tok.line, tok.col, node, idx)

            return node

        # -- grouped expression: ( expr ) --
        if tok.type == "LPAREN":
            self._advance()
            expr = self._parse_expr()
            self._expect("RPAREN")
            # still allow indexing after a grouped expr
            while self._match_type("LBRACKET"):
                self._advance()
                idx = self._parse_expr()
                self._expect("RBRACKET")
                expr = Index(tok.line, tok.col, expr, idx)
            return expr

        # -- list literal: [ expr, ... ] --
        if tok.type == "LBRACKET":
            self._advance()
            elements = self._parse_args()
            self._expect("RBRACKET")
            return ListLit(tok.line, tok.col, elements)

        # -- dict literal: { expr: expr, ... } --
        if tok.type == "LBRACE":
            self._advance()
            entries = self._parse_dict_entries()
            self._expect("RBRACE")
            return DictLit(tok.line, tok.col, entries)

        raise ParseError(
            f"Unexpected token {tok.type!r} '{tok.value}' in expression",
            tok.line, tok.col,
        )

    # ------------------------------------------------------------------
    # Argument list  (expr (',' expr)*)
    # ------------------------------------------------------------------

    def _parse_args(self) -> Tuple[Node, ...]:
        """Parse a comma-separated list of expressions (may be empty)."""
        args = []
        # empty list / no args
        if self._match_type("RPAREN") or self._match_type("RBRACKET"):
            return ()
        args.append(self._parse_expr())
        while self._match_type("COMMA"):
            self._advance()
            args.append(self._parse_expr())
        return tuple(args)

    # ------------------------------------------------------------------
    # Dict entries  (expr ':' expr (',' expr ':' expr)*)
    # ------------------------------------------------------------------

    def _parse_dict_entries(self) -> Tuple[Tuple[Node, Node], ...]:
        entries = []
        if self._match_type("RBRACE"):
            return ()
        key = self._parse_expr()
        self._expect("COLON")
        val = self._parse_expr()
        entries.append((key, val))
        while self._match_type("COMMA"):
            self._advance()
            if self._match_type("RBRACE"):   # trailing comma
                break
            key = self._parse_expr()
            self._expect("COLON")
            val = self._parse_expr()
            entries.append((key, val))
        return tuple(entries)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse(source: str) -> Tuple[Node, ...]:
    """
    Lex and parse *source*, returning a tuple of top-level AST nodes.
    Raises LexError or ParseError on malformed input.
    """
    tokens = tokenize(source)
    return Parser(tokens).parse()