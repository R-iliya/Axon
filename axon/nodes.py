# axon/nodes.py

# -------------------
# Expression Nodes
# -------------------
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

# -------------------
# Statement Nodes
# -------------------
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
