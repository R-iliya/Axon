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

class BooleanNode:
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
        if self.op == 'and': return left and right
        if self.op == 'or': return left or right
        raise ValueError(f"Unknown operator {self.op}")

class UnaryOpNode:
    def __init__(self, op, expr):
        self.op = op
        self.expr = expr
    def eval(self, context):
        val = self.expr.eval(context)
        if self.op == '-': return -val
        if self.op == 'not': return not val
        raise ValueError(f"Unknown unary operator {self.op}")

class ListNode:
    def __init__(self, elements):
        self.elements = elements
    def eval(self, context):
        return [e.eval(context) for e in self.elements]

class IndexNode:
    def __init__(self, collection, index):
        self.collection = collection
        self.index = index
    def eval(self, context):
        coll = self.collection.eval(context)
        idx = self.index.eval(context)
        return coll[idx]

class DictNode:
    def __init__(self, entries):
        self.entries = entries  # list of (key, value) tuples
    def eval(self, context):
        return {k.eval(context): v.eval(context) for k, v in self.entries}

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
