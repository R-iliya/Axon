# axon/nodes.py

import os

# -----------------------------
# Expressions
# -----------------------------
class NumberNode:
    def __init__(self, value):
        self.value = value
    def eval(self, context):
        return self.value

class StringNode:
    def __init__(self, value):
        self.value = value
    def eval(self, context):
        return self.value

class VariableNode:
    def __init__(self, name):
        self.name = name
    def eval(self, context):
        return context.get(self.name, 0)

class BinOpNode:
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right
    def eval(self, context):
        left = self.left.eval(context)
        right = self.right.eval(context)
        if self.op == '+': return left + right
        if self.op == '-': return left - right
        if self.op == '*': return left * right
        if self.op == '/': return left / right
        if self.op == '==': return left == right
        if self.op == '!=': return left != right
        if self.op == '<': return left < right
        if self.op == '>': return left > right
        if self.op == '<=': return left <= right
        if self.op == '>=': return left >= right
        raise ValueError(f"Unknown operator {self.op}")

# -----------------------------
# Statements
# -----------------------------
class PrintNode:
    def __init__(self, expr):
        self.expr = expr
    def eval(self, context):
        print(self.expr.eval(context))

class LetNode:
    def __init__(self, name, expr):
        self.name = name
        self.expr = expr
    def eval(self, context):
        context[self.name] = self.expr.eval(context)

class ClearNode:
    def eval(self, context):
        os.system('cls' if os.name == 'nt' else 'clear')

class IfNode:
    def __init__(self, condition, true_body, false_body=None):
        self.condition = condition
        self.true_body = true_body
        self.false_body = false_body
    def eval(self, context):
        if self.condition.eval(context):
            for stmt in self.true_body:
                stmt.eval(context)
        elif self.false_body:
            for stmt in self.false_body:
                stmt.eval(context)

class WhileNode:
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body
    def eval(self, context):
        while self.condition.eval(context):
            for stmt in self.body:
                stmt.eval(context)

class ForNode:
    def __init__(self, var_name, start_expr, end_expr, body):
        self.var_name = var_name
        self.start_expr = start_expr
        self.end_expr = end_expr
        self.body = body
    def eval(self, context):
        start = self.start_expr.eval(context)
        end = self.end_expr.eval(context)
        for i in range(start, end):
            context[self.var_name] = i
            for stmt in self.body:
                stmt.eval(context)

# -----------------------------
# Functions
# -----------------------------
class FunctionNode:
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body
    def eval(self, context):
        context[self.name] = self

class CallNode:
    def __init__(self, name, args):
        self.name = name
        self.args = args
    def eval(self, context):
        func = context.get(self.name)
        if not isinstance(func, FunctionNode):
            raise ValueError(f"{self.name} is not a function")
        local_ctx = context.copy()
        for p, a in zip(func.params, self.args):
            local_ctx[p] = a.eval(context)
        result = None
        for stmt in func.body:
            result = stmt.eval(local_ctx)
        return result

class ReturnNode:
    def __init__(self, expr):
        self.expr = expr
    def eval(self, context):
        return self.expr.eval(context)
