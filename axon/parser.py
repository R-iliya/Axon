# axon/parser.py

from axon.lexer import tokenize
from axon.nodes import NumberNode, StringNode, VariableNode, PrintNode, LetNode, BinOpNode, FunctionNode, CallNode

class ParseError(Exception):
    pass

class Parser:
    def __init__(self, code):
        self.tokens = tokenize(code)
        self.pos = 0

    def current_token(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def advance(self):
        self.pos += 1

    # --- Expression parsing (numbers, strings, vars, binary ops) ---
    def parse_expression(self):
        left = self.parse_term()
        token = self.current_token()
        while token and token.type == 'OP' and token.value in ('+', '-'):
            op = token.value
            self.advance()
            right = self.parse_term()
            left = BinOpNode(left, op, right)
            token = self.current_token()
        return left

    def parse_term(self):
        left = self.parse_factor()
        token = self.current_token()
        while token and token.type == 'OP' and token.value in ('*', '/'):
            op = token.value
            self.advance()
            right = self.parse_factor()
            left = BinOpNode(left, op, right)
            token = self.current_token()
        return left

    def parse_factor(self):
        token = self.current_token()
        if token.type == 'NUMBER':
            self.advance()
            return NumberNode(token.value)
        elif token.type == 'STRING':
            self.advance()
            return StringNode(token.value)
        elif token.type == 'IDENT':
            self.advance()
            next_token = self.current_token()
            # function call
            if next_token and next_token.type == 'LPAREN':
                self.advance()  # skip '('
                args = []
                while self.current_token().type != 'RPAREN':
                    args.append(self.parse_expression())
                    if self.current_token().type == 'COMMA':
                        self.advance()
                self.advance()  # skip ')'
                return CallNode(token.value, args)
            else:
                return VariableNode(token.value)
        elif token.type == 'LPAREN':
            self.advance()
            expr = self.parse_expression()
            if self.current_token().type != 'RPAREN':
                raise ParseError(f"Expected ')' at line {token.line}")
            self.advance()
            return expr
        else:
            raise ParseError(f"Unexpected token {token}")

    # --- Statement parsing ---
    def parse_statement(self):
        token = self.current_token()
        if token.type == 'IDENT' and token.value == 'print':
            self.advance()
            if self.current_token().type != 'LPAREN':
                raise ParseError("Expected '(' after print")
            self.advance()
            expr = self.parse_expression()
            if self.current_token().type != 'RPAREN':
                raise ParseError("Expected ')' after print expression")
            self.advance()
            if self.current_token().type != 'SEMICOLON':
                raise ParseError("Expected ';' after print statement")
            self.advance()
            return PrintNode(expr)

        elif token.type == 'IDENT' and token.value == 'let':
            self.advance()
            var_name = self.current_token().value
            self.advance()
            if self.current_token().type != 'EQ':
                raise ParseError("Expected '=' in let statement")
            self.advance()
            expr = self.parse_expression()
            if self.current_token().type != 'SEMICOLON':
                raise ParseError("Expected ';' after let statement")
            self.advance()
            return LetNode(var_name, expr)

        # TODO: add fn definition parsing here in next step
        else:
            raise ParseError(f"Unknown statement: {token}")

    # --- Parse all statements ---
    def parse(self):
        stmts = []
        while self.current_token() is not None:
            stmts.append(self.parse_statement())
        return stmts
