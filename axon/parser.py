from axon.lexer import tokenize
from axon.nodes import (
    NumberNode, StringNode, BooleanNode, VariableNode,
    BinOpNode, UnaryOpNode, ListNode, IndexNode, DictNode,
    PrintNode, LetNode, ClearNode, IfNode, WhileNode, ForNode,
    BreakNode, ContinueNode, FunctionNode, CallNode, ReturnNode
)

class ParseError(Exception):
    pass

class Parser:
    def __init__(self, code):
        self.tokens = tokenize(code)
        self.pos = 0

    def current_token(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self):
        self.pos += 1

    # -----------------------
    # Expression Parsing
    # -----------------------

    def consume_semicolon(self):
        """Advance past a semicolon, or raise error if missing."""
        token = self.current_token()
        if not token or token.type != 'SEMICOLON':
            raise ParseError(f"Expected ';' at the end of statement, got {token}")
        self.advance()


    def parse_expression(self, stop_tokens=None):
        stop_tokens = stop_tokens or []
        left = self.parse_logic_term(stop_tokens)
        token = self.current_token()
        while token and token.type not in stop_tokens:
            if token.type == 'OP' and token.value in ('or',):
                op = token.value
                self.advance()
                right = self.parse_logic_term(stop_tokens)
                left = BinOpNode(left, op, right)
                token = self.current_token()
            else:
                break
        return left

    def parse_logic_term(self, stop_tokens=None):
        stop_tokens = stop_tokens or []
        left = self.parse_comparison(stop_tokens)
        token = self.current_token()
        while token and token.type == 'OP' and token.value == 'and':
            op = token.value
            self.advance()
            right = self.parse_comparison(stop_tokens)
            left = BinOpNode(left, op, right)
            token = self.current_token()
        return left

    def parse_comparison(self, stop_tokens=None):
        stop_tokens = stop_tokens or []
        left = self.parse_term(stop_tokens)
        token = self.current_token()
        while token and token.type == 'OP' and token.value in ('==', '!=', '<', '>', '<=', '>='):
            op = token.value
            self.advance()
            right = self.parse_term(stop_tokens)
            left = BinOpNode(left, op, right)
            token = self.current_token()
        return left

    def parse_term(self, stop_tokens=None):
        stop_tokens = stop_tokens or []
        left = self.parse_factor_term(stop_tokens)  # <--- changed here
        token = self.current_token()
        while token and token.type == 'OP' and token.value in ('+', '-'):
            op = token.value
            self.advance()
            right = self.parse_factor_term(stop_tokens)  # <--- changed here
            left = BinOpNode(left, op, right)
            token = self.current_token()
        return left

    def parse_factor_term(self, stop_tokens=None):
        """Handles *, /, % operators with correct precedence"""
        stop_tokens = stop_tokens or []
        left = self.parse_factor(stop_tokens)
        token = self.current_token()
        while token and token.type == 'OP' and token.value in ('*', '/', '%'):
            op = token.value
            self.advance()
            right = self.parse_factor(stop_tokens)
            left = BinOpNode(left, op, right)
            token = self.current_token()
        return left

    def parse_factor(self, stop_tokens=None):
        stop_tokens = stop_tokens or []
        token = self.current_token()
        if not token or token.type in stop_tokens:
            return None

        if token.type == 'OP' and token.value in ('-', 'not'):
            op = token.value
            self.advance()
            expr = self.parse_factor(stop_tokens)
            return UnaryOpNode(op, expr)
        elif token.type == 'NUMBER':
            self.advance()
            return NumberNode(token.value)
        elif token.type == 'STRING':
            self.advance()
            return StringNode(token.value)
        elif token.type == 'IDENT':
            if token.value in ('True', 'False'):
                self.advance()
                return BooleanNode(token.value == 'True')

            self.advance()
            next_token = self.current_token()

            # function call
            if next_token and next_token.type == 'LPAREN':
                self.advance()
                args = []
                while self.current_token() and self.current_token().type != 'RPAREN':
                    args.append(self.parse_expression(stop_tokens=['COMMA', 'RPAREN']))
                    if self.current_token() and self.current_token().type == 'COMMA':
                        self.advance()
                if not self.current_token() or self.current_token().type != 'RPAREN':
                    raise ParseError("Expected ')' after function call")
                self.advance()
                return CallNode(token.value, args)

            # array indexing
            elif next_token and next_token.type == 'LBRACKET':
                collection = VariableNode(token.value)
                while self.current_token() and self.current_token().type == 'LBRACKET':
                    self.advance()
                    index_expr = self.parse_expression(stop_tokens=['RBRACKET'])
                    if not self.current_token() or self.current_token().type != 'RBRACKET':
                        raise ParseError("Expected ']' for index")
                    self.advance()
                    collection = IndexNode(collection, index_expr)
                return collection
            else:
                return VariableNode(token.value)

        elif token.type == 'LPAREN':
            self.advance()
            expr = self.parse_expression(stop_tokens=stop_tokens + ['RPAREN'])
            if not self.current_token() or self.current_token().type != 'RPAREN':
                raise ParseError("Expected ')' after expression")
            self.advance()
            return expr

        elif token.type == 'LBRACKET':  # list literal
            self.advance()
            elements = []
            while self.current_token() and self.current_token().type != 'RBRACKET':
                elements.append(self.parse_expression(stop_tokens=['COMMA', 'RBRACKET']))
                if self.current_token() and self.current_token().type == 'COMMA':
                    self.advance()
            if not self.current_token() or self.current_token().type != 'RBRACKET':
                raise ParseError("Expected ']' after list")
            self.advance()
            return ListNode(elements)

        elif token.type == 'LBRACE':  # dict literal
            self.advance()
            entries = []
            while self.current_token() and self.current_token().type != 'RBRACE':
                key = self.parse_expression(stop_tokens=['COLON'])
                if not self.current_token() or self.current_token().type != 'COLON':
                    raise ParseError("Expected ':' in dict entry")
                self.advance()
                value = self.parse_expression(stop_tokens=['COMMA', 'RBRACE'])
                entries.append((key, value))
                if self.current_token() and self.current_token().type == 'COMMA':
                    self.advance()
            if not self.current_token() or self.current_token().type != 'RBRACE':
                raise ParseError("Expected '}' after dict")
            self.advance()
            return DictNode(entries)

        else:
            raise ParseError(f"Unexpected token {token}")

    # -----------------------
    # Statement Parsing
    # -----------------------
    def parse_statement(self):
        token = self.current_token()
        if not token:
            return None

        # --- keywords ---
        if token.value == 'print':
            self.advance()
            self.expect('LPAREN')
            expr = self.parse_expression(stop_tokens=['RPAREN'])
            self.expect('RPAREN')
            self.consume_semicolon()
            return PrintNode(expr)

        elif token.value == 'let':
            self.advance()
            var_name = self.expect('IDENT').value
            self.expect('EQ')
            expr = self.parse_expression(stop_tokens=['SEMICOLON'])
            self.consume_semicolon()
            return LetNode(var_name, expr)

        elif token.value == 'cls':
            self.advance()
            self.consume_semicolon()
            return ClearNode()

        elif token.value == 'break':
            self.advance()
            self.consume_semicolon()
            return BreakNode()

        elif token.value == 'continue':
            self.advance()
            self.consume_semicolon()
            return ContinueNode()

        elif token.value == 'return':
            self.advance()
            expr = self.parse_expression(stop_tokens=['SEMICOLON'])
            self.consume_semicolon()
            return ReturnNode(expr)

        elif token.value == 'true':
            self.advance()
            self.consume_semicolon()
            return BooleanNode(True)

        elif token.value == 'false':
            self.advance()
            self.consume_semicolon()
            return BooleanNode(False)

        # --- bare assignment x = 5; ---
        elif token.type == 'IDENT':
            next_token = self.peek_next()
            if next_token and next_token.type == 'EQ':
                var_name = token.value
                self.advance()
                self.advance()
                expr = self.parse_expression(stop_tokens=['SEMICOLON'])
                self.consume_semicolon()
                return LetNode(var_name, expr)

        # --- top-level expressions ---
        expr = self.parse_expression(stop_tokens=['SEMICOLON'])
        self.consume_semicolon()
        return expr

    def parse(self):
        """Parse all statements in the code and return a list of statement nodes."""
        statements = []
        while self.current_token():
            stmt = self.parse_statement()
            if stmt is not None:
                statements.append(stmt)
        return statements

    def expect(self, token_type):
        token = self.current_token()
        if not token or token.type != token_type:
            raise ParseError(f"Expected token type {token_type}, got {token}")
        self.advance()
        return token
    
def parse_text(code):
    """
    Entry point for parsing Axon source code.
    Returns a list of statement nodes.
    """
    parser = Parser(code)
    return parser.parse()
