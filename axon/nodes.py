# axon/nodes.py

# ---------- Expressions ----------
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
        raise ValueError(f"Unknown operator {self.op}")

# ---------- Statements ----------
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
        # new local context for function call
        local_ctx = context.copy()
        for p, a in zip(func.params, self.args):
            local_ctx[p] = a.eval(context)
        result = None
        for stmt in func.body:
            result = stmt.eval(local_ctx)
        return result
