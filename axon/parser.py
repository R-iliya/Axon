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
    def __init__(self, code: str):
        self.tokens = tokenize(code)
        self.pos = 0

    def current_token(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def advance(self):
        self.pos += 1

    # -----------------------
    # Token helpers (flexible)
    # -----------------------
    def is_op(self, token, vals):
        """Token may be type 'OP' with token.value or specific token.type names"""
        if token is None:
            return False
        if token.type == "OP" and token.value in vals:
            return True
        if token.type in vals:
            return True
        return False

    # -----------------------
    # Expression Parsing (precedence)
    # or -> and -> equality -> add/sub -> mul/div -> unary -> primary
    # -----------------------
    def parse_expression(self):
        return self.parse_or()

    def parse_or(self):
        node = self.parse_and()
        while True:
            t = self.current_token()
            if t and (t.type == "IDENT" and t.value == "or" or (t.type == "OP" and t.value == "or")):
                self.advance()
                right = self.parse_and()
                node = BinOpNode(node, "or", right)
            else:
                break
        return node

    def parse_and(self):
        node = self.parse_equality()
        while True:
            t = self.current_token()
            if t and (t.type == "IDENT" and t.value == "and" or (t.type == "OP" and t.value == "and")):
                self.advance()
                right = self.parse_equality()
                node = BinOpNode(node, "and", right)
            else:
                break
        return node

    def parse_equality(self):
        node = self.parse_add()
        while True:
            t = self.current_token()
            if t and self.is_op(t, ("==", "!=")):
                op = t.value if t.type == "OP" else t.type
                self.advance()
                right = self.parse_add()
                node = BinOpNode(node, op, right)
            # also support token types named EQEQ/NOTEQ if lexer had them
            elif t and t.type in ("EQEQ", "NOTEQ"):
                op = "==" if t.type == "EQEQ" else "!="
                self.advance()
                right = self.parse_add()
                node = BinOpNode(node, op, right)
            else:
                break
        return node

    def parse_add(self):
        node = self.parse_term()
        while True:
            t = self.current_token()
            if t and self.is_op(t, ("+", "-")):
                op = t.value if t.type == "OP" else t.type
                # normalize op to actual symbol if token.type is PLUS/MINUS
                if op in ("PLUS", "MINUS"):
                    op = "+" if op == "PLUS" else "-"
                self.advance()
                right = self.parse_term()
                node = BinOpNode(node, op, right)
            else:
                break
        return node

    def parse_term(self):
        node = self.parse_factor()
        while True:
            t = self.current_token()
            if t and self.is_op(t, ("*", "/")):
                op = t.value if t.type == "OP" else t.type
                if op in ("STAR", "SLASH"):
                    op = "*" if op == "STAR" else "/"
                self.advance()
                right = self.parse_factor()
                node = BinOpNode(node, op, right)
            else:
                break
        return node

    def parse_factor(self):
        t = self.current_token()
        if t is None:
            raise ParseError("Unexpected end of input in expression")

        # unary: - , not
        if (t.type == "OP" and t.value == "-") or (t.type == "OP" and t.value == "not") or (t.type == "IDENT" and t.value == "not"):
            op = t.value if t.type == "OP" else t.value
            self.advance()
            expr = self.parse_factor()
            return UnaryOpNode(op, expr)

        # literals
        if t.type == "NUMBER":
            self.advance()
            return NumberNode(t.value)
        if t.type == "STRING":
            self.advance()
            return StringNode(t.value)
        if t.type == "IDENT" and t.value in ("true", "false"):
            self.advance()
            return BooleanNode(t.value == "true")

        # grouped expression
        if t.type == "LPAREN":
            self.advance()
            expr = self.parse_expression()
            if not self.current_token() or self.current_token().type != "RPAREN":
                raise ParseError("Expected ')' after expression")
            self.advance()
            return expr

        # list literal
        if t.type == "LBRACKET":
            self.advance()
            elems = []
            if not self.current_token():
                raise ParseError("Unexpected EOF in list literal")
            while self.current_token().type != "RBRACKET":
                elems.append(self.parse_expression())
                if self.current_token() and self.current_token().type == "COMMA":
                    self.advance()
                else:
                    break
            if not self.current_token() or self.current_token().type != "RBRACKET":
                raise ParseError("Expected ']' to close list literal")
            self.advance()
            return ListNode(elems)

        # dict literal
        if t.type == "LBRACE":
            self.advance()
            entries = []
            if not self.current_token():
                raise ParseError("Unexpected EOF in dict literal")
            while self.current_token().type != "RBRACE":
                key = self.parse_expression()
                if not self.current_token() or self.current_token().type != "COLON":
                    raise ParseError("Expected ':' in dict entry")
                self.advance()
                value = self.parse_expression()
                entries.append((key, value))
                if self.current_token() and self.current_token().type == "COMMA":
                    self.advance()
                else:
                    break
            if not self.current_token() or self.current_token().type != "RBRACE":
                raise ParseError("Expected '}' to close dict literal")
            self.advance()
            return DictNode(entries)

        # identifier: variable, function call, indexing
        if t.type == "IDENT":
            name = t.value
            self.advance()
            # function call
            if self.current_token() and self.current_token().type == "LPAREN":
                self.advance()  # skip '('
                args = []
                if not self.current_token():
                    raise ParseError("Unexpected EOF in call")
                while self.current_token().type != "RPAREN":
                    args.append(self.parse_expression())
                    if self.current_token() and self.current_token().type == "COMMA":
                        self.advance()
                    else:
                        break
                if not self.current_token() or self.current_token().type != "RPAREN":
                    raise ParseError("Expected ')' after function call")
                self.advance()
                return CallNode(name, args)
            # indexing: name[expr][expr]...
            node = VariableNode(name)
            while self.current_token() and self.current_token().type == "LBRACKET":
                self.advance()
                idx = self.parse_expression()
                if not self.current_token() or self.current_token().type != "RBRACKET":
                    raise ParseError("Expected ']' after index expression")
                self.advance()
                node = IndexNode(node, idx)
            return node

        raise ParseError(f"Unexpected token in factor: {t}")

    # -----------------------
    # Statements
    # -----------------------
    def parse_statement(self):
        t = self.current_token()
        if t is None:
            raise ParseError("Unexpected end of input")

        # non-IDENT starters: allow e.g. '}' etc to be handled by caller
        if t.type == "SEMICOLON":
            # empty statement; consume and return None
            self.advance()
            return None

        # --- print ---
        if t.type == "IDENT" and t.value == "print":
            self.advance()
            if not self.current_token() or self.current_token().type != "LPAREN":
                raise ParseError("Expected '(' after print")
            self.advance()
            expr = self.parse_expression()
            if not self.current_token() or self.current_token().type != "RPAREN":
                raise ParseError("Expected ')' after print")
            self.advance()
            if not self.current_token() or self.current_token().type != "SEMICOLON":
                raise ParseError("Expected ';' after print")
            self.advance()
            return PrintNode(expr)

        # --- let (explicit) ---
        if t.type == "IDENT" and t.value == "let":
            self.advance()
            if not self.current_token() or self.current_token().type != "IDENT":
                raise ParseError("Expected identifier after let")
            name = self.current_token().value
            self.advance()
            if not self.current_token() or self.current_token().type != "EQ":
                raise ParseError("Expected '=' in let statement")
            self.advance()
            expr = self.parse_expression()
            if not self.current_token() or self.current_token().type != "SEMICOLON":
                raise ParseError("Expected ';' after let")
            self.advance()
            return LetNode(name, expr)

        # --- bare assignment: x = expr; ---
        if t.type == "IDENT":
            # lookahead: identifier followed by EQ -> assignment
            name = t.value
            nextt = self.tokens[self.pos + 1] if (self.pos + 1) < len(self.tokens) else None
            if nextt and nextt.type == "EQ":
                # consume name and '='
                self.advance()
                self.advance()
                expr = self.parse_expression()
                if not self.current_token() or self.current_token().type != "SEMICOLON":
                    raise ParseError(f"Expected ';' after assignment, got {self.current_token()}")
                self.advance()
                return LetNode(name, expr)
            # otherwise fallthrough - maybe it's a statement starting with identifier (e.g., function call as statement)
            # handle function call as statement: foo(...);
            # treat simple identifier-starting statements by trying to parse an expression then require semicolon
            # parse expression starting from current position (we already at IDENT), but factor already consumed the IDENT
            # so reparse: step back one token and parse expression
            # (simpler approach: parse expression from current position by not advancing above)
            # We'll parse a general expression statement: expr;
            expr = self.parse_expression()
            if not self.current_token() or self.current_token().type != "SEMICOLON":
                raise ParseError(f"Expected ';' after expression statement, got {self.current_token()}")
            self.advance()
            return expr  # expression statement (may be CallNode)

        # --- cls ---
        if t.type == "IDENT" and t.value == "cls":
            self.advance()
            if not self.current_token() or self.current_token().type != "SEMICOLON":
                raise ParseError("Expected ';' after cls")
            self.advance()
            return ClearNode()

        # --- break ---
        if t.type == "IDENT" and t.value == "break":
            self.advance()
            if not self.current_token() or self.current_token().type != "SEMICOLON":
                raise ParseError("Expected ';' after break")
            self.advance()
            return BreakNode()

        # --- continue ---
        if t.type == "IDENT" and t.value == "continue":
            self.advance()
            if not self.current_token() or self.current_token().type != "SEMICOLON":
                raise ParseError("Expected ';' after continue")
            self.advance()
            return ContinueNode()

        # --- if / else ---
        if t.type == "IDENT" and t.value == "if":
            self.advance()
            if not self.current_token() or self.current_token().type != "LPAREN":
                raise ParseError("Expected '(' after if")
            self.advance()
            cond = self.parse_expression()
            if not self.current_token() or self.current_token().type != "RPAREN":
                raise ParseError("Expected ')' after if condition")
            self.advance()
            if not self.current_token() or self.current_token().type != "LBRACE":
                raise ParseError("Expected '{' after if")
            self.advance()
            true_body = self.parse_block()
            false_body = None
            # optional else
            if self.current_token() and self.current_token().type == "IDENT" and self.current_token().value == "else":
                self.advance()
                if not self.current_token() or self.current_token().type != "LBRACE":
                    raise ParseError("Expected '{' after else")
                self.advance()
                false_body = self.parse_block()
            return IfNode(cond, true_body, false_body)

        # --- while ---
        if t.type == "IDENT" and t.value == "while":
            self.advance()
            if not self.current_token() or self.current_token().type != "LPAREN":
                raise ParseError("Expected '(' after while")
            self.advance()
            cond = self.parse_expression()
            if not self.current_token() or self.current_token().type != "RPAREN":
                raise ParseError("Expected ')' after while condition")
            self.advance()
            if not self.current_token() or self.current_token().type != "LBRACE":
                raise ParseError("Expected '{' after while")
            self.advance()
            body = self.parse_block()
            return WhileNode(cond, body)

        # --- for i = start; end { body } ---
        if t.type == "IDENT" and t.value == "for":
            self.advance()
            if not self.current_token() or self.current_token().type != "IDENT":
                raise ParseError("Expected identifier after for")
            var_name = self.current_token().value
            self.advance()
            if not self.current_token() or self.current_token().type != "EQ":
                raise ParseError("Expected '=' in for header")
            self.advance()
            start_expr = self.parse_expression()
            if not self.current_token() or self.current_token().type != "SEMICOLON":
                raise ParseError("Expected ';' after for start expr")
            self.advance()
            end_expr = self.parse_expression()
            if not self.current_token() or self.current_token().type != "LBRACE":
                raise ParseError("Expected '{' after for range")
            self.advance()
            body = self.parse_block()
            return ForNode(var_name, start_expr, end_expr, body)

        # --- function definition: fn name(param, ...) { body } ---
        if t.type == "IDENT" and t.value == "fn":
            self.advance()
            if not self.current_token() or self.current_token().type != "IDENT":
                raise ParseError("Expected function name after fn")
            name = self.current_token().value
            self.advance()
            if not self.current_token() or self.current_token().type != "LPAREN":
                raise ParseError("Expected '(' after function name")
            self.advance()
            params = []
            if self.current_token() and self.current_token().type != "RPAREN":
                while True:
                    if not self.current_token() or self.current_token().type != "IDENT":
                        raise ParseError("Expected parameter name")
                    params.append(self.current_token().value)
                    self.advance()
                    if not self.current_token():
                        raise ParseError("Unexpected EOF in parameter list")
                    if self.current_token().type == "COMMA":
                        self.advance()
                        continue
                    elif self.current_token().type == "RPAREN":
                        break
                    else:
                        raise ParseError("Expected ',' or ')' in parameter list")
            # consume RPAREN
            if not self.current_token() or self.current_token().type != "RPAREN":
                raise ParseError("Expected ')' after parameters")
            self.advance()
            if not self.current_token() or self.current_token().type != "LBRACE":
                raise ParseError("Expected '{' to start function body")
            self.advance()
            body = self.parse_block()
            return FunctionNode(name, params, body)

        # --- return ---
        if t.type == "IDENT" and t.value == "return":
            self.advance()
            expr = self.parse_expression()
            if not self.current_token() or self.current_token().type != "SEMICOLON":
                raise ParseError("Expected ';' after return")
            self.advance()
            return ReturnNode(expr)

        # unknown
        raise ParseError(f"Unknown statement start: {t}")

    def parse_block(self):
        stmts = []
        # empty body allowed
        while self.current_token() and self.current_token().type != "RBRACE":
            stmt = self.parse_statement()
            # ignore None (empty statements)
            if stmt is not None:
                stmts.append(stmt)
        if not self.current_token() or self.current_token().type != "RBRACE":
            raise ParseError("Expected '}' at end of block")
        self.advance()  # skip RBRACE
        return stmts

    def parse(self):
        stmts = []
        while self.current_token() and self.current_token().type != "EOF":
            stmt = self.parse_statement()
            if stmt is not None:
                stmts.append(stmt)
        return stmts

# Public API
def parse_text(source_code: str):
    p = Parser(source_code)
    return p.parse()
