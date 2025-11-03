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
        """Advance past a semicolon, whether it's SEMICOLON or OP ';'"""
        token = self.current_token()
        if not token:
            raise ParseError("Expected ';', got EOF")
        if token.type == 'SEMICOLON':
            self.advance()
        elif token.type == 'OP' and token.value == ';':
            self.advance()
        else:
            raise ParseError(f"Expected ';', got {token}")

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
        while token and token.type not in stop_tokens and token.type == 'OP' and token.value == 'and':
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
        while token and token.type not in stop_tokens and token.type == 'OP' and token.value in ('==', '!=', '<', '>', '<=', '>='):
            op = token.value
            self.advance()
            right = self.parse_term(stop_tokens)
            left = BinOpNode(left, op, right)
            token = self.current_token()
        return left

    def parse_term(self, stop_tokens=None):
        stop_tokens = stop_tokens or []
        left = self.parse_factor(stop_tokens)
        token = self.current_token()
        while token and token.type not in stop_tokens and token.type == 'OP' and token.value in ('+', '-'):
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
            if token.value in ('true', 'false'):
                self.advance()
                return BooleanNode(token.value == 'true')

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
        if not token or token.type != 'IDENT':
            raise ParseError(f"Expected statement, got {token}")

        # --- print ---
        if token.value == 'print':
            self.advance()
            if not self.current_token() or self.current_token().type != 'LPAREN':
                raise ParseError("Expected '(' after print")
            self.advance()
            expr = self.parse_expression(stop_tokens=['RPAREN', 'SEMICOLON'])
            if not self.current_token() or self.current_token().type != 'RPAREN':
                raise ParseError("Expected ')' after print")
            self.advance()
            self.consume_semicolon()
            return PrintNode(expr)

        # --- let ---
        elif token.value == 'let':
            self.advance()
            if not self.current_token() or self.current_token().type != 'IDENT':
                raise ParseError("Expected variable name after let")
            var_name = self.current_token().value
            self.advance()
            if not self.current_token() or self.current_token().type != 'EQ':
                raise ParseError("Expected '=' in let statement")
            self.advance()
            expr = self.parse_expression(stop_tokens=['SEMICOLON'])
            self.consume_semicolon()
            return LetNode(var_name, expr)

        # --- cls ---
        elif token.value == 'cls':
            self.advance()
            self.consume_semicolon()
            return ClearNode()

        # --- break ---
        elif token.value == 'break':
            self.advance()
            self.consume_semicolon()
            return BreakNode()

        # --- continue ---
        elif token.value == 'continue':
            self.advance()
            self.consume_semicolon()
            return ContinueNode()

        # --- if/else ---
        elif token.value == 'if':
            self.advance()
            condition = self.parse_expression(stop_tokens=['LBRACE'])
            if not self.current_token() or self.current_token().type != 'LBRACE':
                raise ParseError("Expected '{' after if condition")
            self.advance()
            true_body = self.parse_block()
            false_body = None
            if self.current_token() and self.current_token().type == 'IDENT' and self.current_token().value == 'else':
                self.advance()
                if not self.current_token() or self.current_token().type != 'LBRACE':
                    raise ParseError("Expected '{' after else")
                self.advance()
                false_body = self.parse_block()
            return IfNode(condition, true_body, false_body)

        # --- while ---
        elif token.value == 'while':
            self.advance()
            condition = self.parse_expression(stop_tokens=['LBRACE'])
            if not self.current_token() or self.current_token().type != 'LBRACE':
                raise ParseError("Expected '{' after while condition")
            self.advance()
            body = self.parse_block()
            return WhileNode(condition, body)

        # --- for ---
        elif token.value == 'for':
            self.advance()
            var_name = self.current_token().value
            self.advance()
            if not self.current_token() or self.current_token().type != 'EQ':
                raise ParseError("Expected '=' after for loop variable")
            self.advance()
            start_expr = self.parse_expression(stop_tokens=['OP'])
            if not self.current_token() or self.current_token().type != 'OP' or self.current_token().value != 'to':
                raise ParseError("Expected 'to' in for loop")
            self.advance()
            end_expr = self.parse_expression(stop_tokens=['LBRACE'])
            if not self.current_token() or self.current_token().type != 'LBRACE':
                raise ParseError("Expected '{' after for loop")
            self.advance()
            body = self.parse_block()
            return ForNode(var_name, start_expr, end_expr, body)

        # --- function ---
        elif token.value == 'fn':
            self.advance()
            func_name = self.current_token().value
            self.advance()
            if not self.current_token() or self.current_token().type != 'LPAREN':
                raise ParseError("Expected '(' after function name")
            self.advance()
            params = []
            while self.current_token() and self.current_token().type != 'RPAREN':
                params.append(self.current_token().value)
                self.advance()
                if self.current_token() and self.current_token().type == 'COMMA':
                    self.advance()
            if not self.current_token() or self.current_token().type != 'RPAREN':
                raise ParseError("Expected ')' after function parameters")
            self.advance()
            if not self.current_token() or self.current_token().type != 'LBRACE':
                raise ParseError("Expected '{' for function body")
            self.advance()
            body = self.parse_block()
            return FunctionNode(func_name, params, body)

        # --- return ---
        elif token.value == 'return':
            self.advance()
            expr = self.parse_expression(stop_tokens=['SEMICOLON'])
            self.consume_semicolon()
            return ReturnNode(expr)

        # --- bare assignment x = 5; ---
        elif token.type == 'IDENT':
            next_token = self.tokens[self.pos + 1] if self.pos + 1 < len(self.tokens) else None
            if next_token and next_token.type == 'EQ':
                var_name = token.value
                self.advance()
                self.advance()
                expr = self.parse_expression(stop_tokens=['SEMICOLON'])
                self.consume_semicolon()
                return LetNode(var_name, expr)

            
    def parse(self):
        """
        Parse the full program and return a list of statement nodes.
        """
        stmts = []
        while self.current_token():
            stmts.append(self.parse_statement())
        return stmts
           
# at the bottom of axon/parser.py
def parse_text(code):
    """
    Entry point for parsing Axon source code.
    Returns a list of statement nodes.
    """
    parser = Parser(code)
    return parser.parse()
