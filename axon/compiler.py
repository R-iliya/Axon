# axon/compiler.py
from typing import List, Tuple, Any, Dict
from axon.ast import *  # noqa: F403, F401
from dataclasses import dataclass
from axon.nodes import *  # noqa: F403, F401

Instruction = Tuple

@dataclass
class CodeObject:
    code: List[Instruction]
    consts: List[Any]
    name: str

def compile_program(prog: Program) -> CodeObject:
    consts: List[Any] = []
    code: List[Instruction] = []

    stmts = prog.statements if hasattr(prog, "statements") else prog

    for stmt in stmts:

        # let x = expr;
        if isinstance(stmt, LetNode):
            code.extend(compile_expr(stmt.expr, consts))
            code.append(("STORE_NAME", stmt.name))

        # print(expr);
        elif isinstance(stmt, PrintNode):
            code.extend(compile_expr(stmt.expr, consts))
            code.append(("PRINT",))
        else:
            raise Exception(f"Unhandled stmt in compiler: {stmt}")

    return CodeObject(code, consts, name="__main__")

def compile_expr(node, consts):

    # number literal
    if isinstance(node, NumberNode):
        idx = add_const(consts, node.value)
        return [("CONST", idx)]

    # string literal
    if isinstance(node, StringNode):
        idx = add_const(consts, node.value)
        return [("CONST", idx)]

    # boolean literal
    if isinstance(node, BooleanNode):
        idx = add_const(consts, node.value)
        return [("CONST", idx)]

    # variable reference
    if isinstance(node, VariableNode):
        return [("LOAD_NAME", node.name)]

    # binary operators
    if isinstance(node, BinOpNode):
        code = []
        code.extend(compile_expr(node.left, consts))
        code.extend(compile_expr(node.right, consts))
        op = node.op

        if op == "+":
            code.append(("BINARY_ADD",))
        elif op == "-":
            code.append(("BINARY_SUB",))
        elif op == "*":
            code.append(("BINARY_MUL",))
        elif op == "/":
            code.append(("BINARY_DIV",))
        else:
            raise Exception(f"Unknown binary op: {op}")

        return code
    raise Exception(f"Unhandled expr: {node}")

def add_const(consts: List[Any], v: Any) -> int:
    consts.append(v)
    return len(consts) - 1