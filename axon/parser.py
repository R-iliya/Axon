from axon.lexer import tokenize, Token
from axon.nodes import NumberNode, StringNode, VariableNode, PrintNode, LetNode


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

    # ====================
    # Expression parser
    # ====================
    def parse_expression(self):
        token = self.current_token()

        if token is None:
            raise ParseError("Unexpected end of input")

        if token.type == 'NUMBER':
            self.advance()
            return NumberNode(token.value)

        elif token.type == 'STRING':
            self.advance()
            return StringNode(token.value)

        elif token.type == 'IDENT':
            self.advance()
            return VariableNode(token.value)

        else:
            raise ParseError(f"Unexpected token at line {token.line} col {token.col}: {token}")

    # ====================
    # Statement parser
    # ====================
    def parse_statement(self):
        token = self.current_token()
        if token is None:
            return None

        # print statement
        if token.type == 'IDENT' and token.value == 'print':
            self.advance()
            # Expect '('
            token = self.current_token()
            if token.type != 'LPAREN':
                raise ParseError(f"Expected '(' after print at line {token.line} col {token.col}")
            self.advance()

            expr = self.parse_expression()

            token = self.current_token()
            if token.type != 'RPAREN':
                raise ParseError(f"Expected ')' after expression at line {token.line} col {token.col}")
            self.advance()

            token = self.current_token()
            if token.type != 'SEMICOLON':
                raise ParseError(f"Expected ';' after print statement at line {token.line} col {token.col}")
            self.advance()

            return PrintNode(expr)

        else:
            raise ParseError(f"Unknown statement at line {token.line} col {token.col}: {token}")

    # ====================
    # Parse all statements
    # ====================
    def parse(self):
        statements = []
        while self.current_token() is not None:
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
        return statements
