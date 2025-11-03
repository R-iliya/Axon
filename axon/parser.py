# axon/parser.py

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
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def advance(self):
        self.pos += 1

    # -----------------------
    # Expression Parsing
    # -----------------------
    def parse_expression(self):
        node = self.parse_term()
        while self.current_token() and self.current_token().type in ('PLUS', 'MINUS'):
            op = self.current_token().type
            self.advance()
            right = self.parse_term()
            node = BinOpNode(left=node, op=op, right=right)
        return node

    def parse_logic_term(self):
        left = self.parse_term()
        token = self.current_token()
        while token and token.type == 'OP' and token.value in ('and',):
            op = token.value
            self.advance()
            right = self.parse_term()
            left = BinOpNode(left, op, right)
            token = self.current_token()
        return left

    def parse_term(self):
        node = self.parse_factor()
        while self.current_token() and (
            (self.current_token().type == 'OP' and self.current_token().value in ('*', '/'))
            or self.current_token().type in ('STAR', 'SLASH')
        ):
            op = self.current_token().value if self.current_token().type == 'OP' else self.current_token().type
            self.advance()
            right = self.parse_factor()
            node = BinOpNode(left=node, op=op, right=right)
        return node

    def parse_factor(self):
        token = self.current_token()
        if token.type == 'OP' and token.value in ('-', 'not'):
            op = token.value
            self.advance()
            expr = self.parse_factor()
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
                self.advance()  # skip '('
                args = []
                while self.current_token().type != 'RPAREN':
                    args.append(self.parse_expression())
                    if self.current_token().type == 'COMMA':
                        self.advance()
                self.advance()  # skip ')'
                return CallNode(token.value, args)
            # array indexing
            elif next_token and next_token.type == 'LBRACKET':
                collection = VariableNode(token.value)
                while self.current_token() and self.current_token().type == 'LBRACKET':
                    self.advance()
                    index_expr = self.parse_expression()
                    if self.current_token().type != 'RBRACKET':
                        raise ParseError("Expected ']' for index")
                    self.advance()
                    collection = IndexNode(collection, index_expr)
                return collection
            else:
                return VariableNode(token.value)

        elif token.type == 'LPAREN':
            self.advance()
            expr = self.parse_expression()
            if self.current_token().type != 'RPAREN':
                raise ParseError("Expected ')'")
            self.advance()
            return expr

        elif token.type == 'LBRACKET':  # list literal
            self.advance()
            elements = []
            while self.current_token().type != 'RBRACKET':
                elements.append(self.parse_expression())
                if self.current_token().type == 'COMMA':
                    self.advance()
            self.advance()
            return ListNode(elements)

        elif token.type == 'LBRACE':  # dict literal
            self.advance()
            entries = []
            while self.current_token().type != 'RBRACE':
                key = self.parse_expression()
                if self.current_token().type != 'COLON':
                    raise ParseError("Expected ':' in dict entry")
                self.advance()
                value = self.parse_expression()
                entries.append((key, value))
                if self.current_token().type == 'COMMA':
                    self.advance()
            self.advance()
            return DictNode(entries)

        else:
            raise ParseError(f"Unexpected token {token}")

    # -----------------------
    # Statement Parsing
    # -----------------------
    def parse_statement(self):
        token = self.current_token()
        if token is None:
            raise ParseError("Unexpected end of input")

        if token.type != 'IDENT':
            raise ParseError(f"Expected statement, got {token}")

        # --- print statement ---
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

        # --- let statement (explicit variable declaration) ---
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

        # --- bare assignment: x = 5; ---
        elif token.type == 'IDENT':
            var_name = token.value
            self.advance()
            # check if it's an assignment
            if self.current_token() and self.current_token().type == 'EQ':
                self.advance()
                expr = self.parse_expression()
                tok = self.current_token()
                if tok is None or tok.type != 'SEMICOLON':
                    raise ParseError(f"Expected ';' after assignment, got {tok}")
                self.advance()
                return LetNode(var_name, expr)
            else:
                raise ParseError(f"Unknown statement: {token}")

        # --- clear screen ---
        elif token.value == 'cls':
            self.advance()
            if self.current_token().type != 'SEMICOLON':
                raise ParseError("Expected ';' after cls")
            self.advance()
            return ClearNode()

        # --- break ---
        elif token.value == 'break':
            self.advance()
            if self.current_token().type != 'SEMICOLON':
                raise ParseError("Expected ';' after break")
            self.advance()
            return BreakNode()

        # --- continue ---
        elif token.value == 'continue':
            self.advance()
            if self.current_token().type != 'SEMICOLON':
                raise ParseError("Expected ';' after continue")
            self.advance()
            return ContinueNode()

        # (IfNode, WhileNode, ForNode, etc. would follow below)
        else:
            raise ParseError(f"Unknown statement: {token}")

    def parse_block(self):
        stmts = []
        while self.current_token().type != 'RBRACE':
            stmts.append(self.parse_statement())
        self.advance()  # skip RBRACE
        return stmts

    def parse(self):
        stmts = []
        while self.current_token() is not None:
            stmts.append(self.parse_statement())
        return stmts

# -----------------------
# Public API Entry Point
# -----------------------
def parse_text(source_code: str):
    """
    Entry point for Axon's parser.
    Takes raw source code as text and returns the parsed AST.
    """
    parser = Parser(source_code)
    return parser.parse()