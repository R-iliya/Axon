# axon/parser.py
from typing import List
from axon.lexer import Token, tokenize
from axon import ast
from axon.ast import *
import sys

class ParseError(Exception):
    pass

class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def current(self) -> Token:
        return self.tokens[self.pos]

    def eat(self, typ: str) -> Token:
        cur = self.current()
        if cur.type == typ:
            self.pos += 1
            return cur
        raise ParseError(f"Expected {typ} at line {cur.line} col {cur.col}, got {cur.type}({cur.value})")

    def parse(self) -> Program:
        stmts = []
        while self.current().type != "EOF":
            if self.current().type == "EOF":
                break
            stmts.append(self.statement())
        return Program(stmts)

    def statement(self):
        cur = self.current()
        # print-statement: print(expr);
        if cur.type == "IDENT" and cur.value == "print":
            tok = self.eat("IDENT")
            self.eat("LPAREN")
            expr = self.expression()
            self.eat("RPAREN")
            self.eat("SEMICOL")
            return Print(expr, tok.line, tok.col)

        # assignment: IDENT = expr;
        if cur.type == "IDENT":
            # lookahead for EQ
            if self.tokens[self.pos + 1].type == "EQ":
                name_tok = self.eat("IDENT")
                self.eat("EQ")
                expr = self.expression()
                self.eat("SEMICOL")
                return Assign(name_tok.value, expr, name_tok.line, name_tok.col)

        raise ParseError(f"Unknown statement at line {cur.line} col {cur.col}: {cur.type}({cur.value})")

    # expression -> term ((+|-) term)*
    def expression(self):
        node = self.term()
        while self.current().type in ("PLUS", "MINUS"):
            op_tok = self.eat(self.current().type)
            right = self.term()
            node = BinOp(node, op_tok.value, right, op_tok.line, op_tok.col)
        return node

    # term -> factor ((*|/) factor)*
    def term(self):
        node = self.factor()
        while self.current().type in ("TIMES", "DIV"):
            op_tok = self.eat(self.current().type)
            right = self.factor()
            node = BinOp(node, op_tok.value, right, op_tok.line, op_tok.col)
        return node

    def factor(self):
        cur = self.current()
        if cur.type == "NUMBER":
            tok = self.eat("NUMBER")
            val = float(tok.value) if "." in tok.value else int(tok.value)
            return Number(val, tok.line, tok.col)
        if cur.type == "IDENT":
            tok = self.eat("IDENT")
            return Var(tok.value, tok.line, tok.col)
        if cur.type == "LPAREN":
            self.eat("LPAREN")
            node = self.expression()
            self.eat("RPAREN")
            return node
        raise ParseError(f"Unexpected token at line {cur.line} col {cur.col}: {cur.type}({cur.value})")

def parse_text(text: str) -> Program:
    tokens = tokenize(text)
    p = Parser(tokens)
    return p.parse()

if __name__ == "__main__":
    import sys
    src = open(sys.argv[1]).read() if len(sys.argv) > 1 else "print(1+2*3);"
    prog = parse_text(src)
    print(prog)
