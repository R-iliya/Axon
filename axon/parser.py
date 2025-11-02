# axon/parser.py

from axon.lexer import tokenize
from axon.nodes import (
    NumberNode, StringNode, VariableNode, PrintNode, LetNode, BinOpNode,
    FunctionNode, CallNode, ClearNode, IfNode, WhileNode, ForNode, ReturnNode
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

    # -------------------
    # Expression parsing
    # -------------------
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

    # -------------------
    # Statement parsing
    # -------------------
    def parse_statement(self):
        token = self.current_token()
        if token.type == 'IDENT':
            if token.value == 'print':
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

            elif token.value == 'let':
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

            elif token.value == 'cls':
                self.advance()
                if self.current_token().type != 'SEMICOLON':
                    raise ParseError("Expected ';' after cls")
                self.advance()
                return ClearNode()

            elif token.value == 'fn':
                self.advance()
                fn_name = self.current_token().value
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
                self.advance()  # skip ')'
                if self.current_token().type != 'LBRACE':
                    raise ParseError("Expected '{' to start function body")
                self.advance()
                body = []
                while self.current_token().type != 'RBRACE':
                    body.append(self.parse_statement())
                self.advance()  # skip '}'
                return FunctionNode(fn_name, params, body)

            elif token.value == 'return':
                self.advance()
                expr = self.parse_expression()
                if self.current_token().type != 'SEMICOLON':
                    raise ParseError("Expected ';' after return statement")
                self.advance()
                return ReturnNode(expr)

            elif token.value == 'if':
                self.advance()
                condition = self.parse_expression()
                if self.current_token().type != 'LBRACE':
                    raise ParseError("Expected '{' after if condition")
                self.advance()
                true_body = []
                while self.current_token().type != 'RBRACE':
                    true_body.append(self.parse_statement())
                self.advance()  # skip '}'
                false_body = None
                next_token = self.current_token()
                if next_token and next_token.type == 'IDENT' and next_token.value == 'else':
                    self.advance()
                    if self.current_token().type != 'LBRACE':
                        raise ParseError("Expected '{' after else")
                    self.advance()
                    false_body = []
                    while self.current_token().type != 'RBRACE':
                        false_body.append(self.parse_statement())
                    self.advance()
                return IfNode(condition, true_body, false_body)

            elif token.value == 'while':
                self.advance()
                condition = self.parse_expression()
                if self.current_token().type != 'LBRACE':
                    raise ParseError("Expected '{' after while condition")
                self.advance()
                body = []
                while self.current_token().type != 'RBRACE':
                    body.append(self.parse_statement())
                self.advance()
                return WhileNode(condition, body)

            elif token.value == 'for':
                self.advance()
                var_name = self.current_token().value
                self.advance()
                if self.current_token().type != 'EQ':
                    raise ParseError("Expected '=' after for variable")
                self.advance()
                start_expr = self.parse_expression()
                if self.current_token().type != 'TO':
                    raise ParseError("Expected 'to' in for loop")
                self.advance()
                end_expr = self.parse_expression()
                if self.current_token().type != 'LBRACE':
                    raise ParseError("Expected '{' after for loop")
                self.advance()
                body = []
                while self.current_token().type != 'RBRACE':
                    body.append(self.parse_statement())
                self.advance()
                return ForNode(var_name, start_expr, end_expr, body)

        raise ParseError(f"Unknown statement: {token}")

    # -------------------
    # Parse all statements
    # -------------------
    def parse(self):
        stmts = []
        while self.current_token() is not None:
            stmts.append(self.parse_statement())
        return stmts
