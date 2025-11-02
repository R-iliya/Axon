# axon/parser.py

from axon.lexer import tokenize
from axon.nodes import (
    NumberNode, StringNode, VariableNode, PrintNode, LetNode,
    BinOpNode, FunctionNode, CallNode, ClearNode, IfNode,
    WhileNode, ForNode, ReturnNode
)

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

    # -----------------------
    # Expression Parsing
    # -----------------------
    def parse_expression(self):
        left = self.parse_term()
        token = self.current_token()
        while token and token.type == 'OP' and token.value in ('+', '-', '==', '!=', '<', '>', '<=', '>='):
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
                self.advance()
                args = []
                while self.current_token().type != 'RPAREN':
                    args.append(self.parse_expression())
                    if self.current_token().type == 'COMMA':
                        self.advance()
                self.advance()
                return CallNode(token.value, args)
            else:
                return VariableNode(token.value)
        elif token.type == 'LPAREN':
            self.advance()
            expr = self.parse_expression()
            if self.current_token().type != 'RPAREN':
                raise ParseError("Expected ')'")
            self.advance()
            return expr
        else:
            raise ParseError(f"Unexpected token {token}")

    # -----------------------
    # Statement Parsing
    # -----------------------
    def parse_statement(self):
        token = self.current_token()
        if token.type != 'IDENT':
            raise ParseError(f"Expected statement, got {token}")

        # --- print ---
        if token.value == 'print':
            self.advance()
            if self.current_token().type != 'LPAREN':
                raise ParseError("Expected '(' after print")
            self.advance()
            expr = self.parse_expression()
            if self.current_token().type != 'RPAREN':
                raise ParseError("Expected ')' after print")
            self.advance()
            if self.current_token().type != 'SEMICOLON':
                raise ParseError("Expected ';' after print")
            self.advance()
            return PrintNode(expr)

        # --- let ---
        elif token.value == 'let':
            self.advance()
            var_name = self.current_token().value
            self.advance()
            if self.current_token().type != 'EQ':
                raise ParseError("Expected '=' in let statement")
            self.advance()
            expr = self.parse_expression()
            if self.current_token().type != 'SEMICOLON':
                raise ParseError("Expected ';' after let")
            self.advance()
            return LetNode(var_name, expr)

        # --- cls ---
        elif token.value == 'cls':
            self.advance()
            if self.current_token().type != 'SEMICOLON':
                raise ParseError("Expected ';' after cls")
            self.advance()
            return ClearNode()

        # --- if / else ---
        elif token.value == 'if':
            self.advance()
            if self.current_token().type != 'LPAREN':
                raise ParseError("Expected '(' after if")
            self.advance()
            condition = self.parse_expression()
            if self.current_token().type != 'RPAREN':
                raise ParseError("Expected ')' after if condition")
            self.advance()
            if self.current_token().type != 'LBRACE':
                raise ParseError("Expected '{' after if condition")
            self.advance()
            true_body = self.parse_block()
            false_body = None
            token = self.current_token()
            if token and token.type == 'IDENT' and token.value == 'else':
                self.advance()
                if self.current_token().type != 'LBRACE':
                    raise ParseError("Expected '{' after else")
                self.advance()
                false_body = self.parse_block()
            return IfNode(condition, true_body, false_body)

        # --- while ---
        elif token.value == 'while':
            self.advance()
            if self.current_token().type != 'LPAREN':
                raise ParseError("Expected '(' after while")
            self.advance()
            condition = self.parse_expression()
            if self.current_token().type != 'RPAREN':
                raise ParseError("Expected ')' after while condition")
            self.advance()
            if self.current_token().type != 'LBRACE':
                raise ParseError("Expected '{' after while condition")
            self.advance()
            body = self.parse_block()
            return WhileNode(condition, body)

        # --- for ---
        elif token.value == 'for':
            self.advance()
            var_name = self.current_token().value
            self.advance()
            if self.current_token().type != 'EQ':
                raise ParseError("Expected '=' in for loop")
            self.advance()
            start_expr = self.parse_expression()
            if self.current_token().type != 'SEMICOLON':
                raise ParseError("Expected ';' after start expr")
            self.advance()
            end_expr = self.parse_expression()
            if self.current_token().type != 'LBRACE':
                raise ParseError("Expected '{' after for loop range")
            self.advance()
            body = self.parse_block()
            return ForNode(var_name, start_expr, end_expr, body)

        # --- function definition ---
        elif token.value == 'fn':
            self.advance()
            name = self.current_token().value
            self.advance()
            if self.current_token().type != 'LPAREN':
                raise ParseError("Expected '(' after function name")
            self.advance()
            params = []
            while self.current_token().type != 'RPAREN':
                params.append(self.current_token().value)
                self.advance()
                if self.current_token().type == 'COMMA':
                    self.advance()
            self.advance()
            if self.current_token().type != 'LBRACE':
                raise ParseError("Expected '{' after function parameters")
            self.advance()
            body = self.parse_block()
            return FunctionNode(name, params, body)

        # --- return ---
        elif token.value == 'return':
            self.advance()
            expr = self.parse_expression()
            if self.current_token().type != 'SEMICOLON':
                raise ParseError("Expected ';' after return")
            self.advance()
            return ReturnNode(expr)

        else:
            raise ParseError(f"Unknown statement: {token}")

    def parse_block(self):
        stmts = []
        while self.current_token().type != 'RBRACE':
            stmts.append(self.parse_statement())
        self.advance()  # skip RBRACE
        return stmts

    # -----------------------
    # Parse all statements
    # -----------------------
    def parse(self):
        stmts = []
        while self.current_token() is not None:
            stmts.append(self.parse_statement())
        return stmts
