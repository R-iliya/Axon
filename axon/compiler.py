# axon/compiler.py
from typing import List, Tuple, Any, Dict
from axon.ast import *
from dataclasses import dataclass
from axon.nodes import LetNode, PrintNode

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
        elif isinstance(stmt, PrintNode):
            code.extend(compile_expr(stmt.expr, consts))
            code.append(("PRINT",))

        # print(expr);
        elif isinstance(stmt, PrintNode):
            code.extend(compile_expr(stmt.expr, consts))
            code.append(("PRINT",))
        else:
            raise Exception(f"Unhandled stmt in compiler: {stmt}")

    return CodeObject(code, consts)

def compile_expr(node, consts: List[Any]) -> List[Instruction]:
    if isinstance(node, Number):
        idx = add_const(consts, node.value)
        return [("CONST", idx)]
    if isinstance(node, Var):
        return [("LOAD_NAME", node.name)]
    if isinstance(node, BinOp):
        code = []
        code.extend(compile_expr(node.left, consts))
        code.extend(compile_expr(node.right, consts))
        if node.op == "+":
            code.append(("BINARY_ADD",))
        elif node.op == "-":
            code.append(("BINARY_SUB",))
        elif node.op == "*":
            code.append(("BINARY_MUL",))
        elif node.op == "/":
            code.append(("BINARY_DIV",))
        else:
            raise Exception(f"Unknown binary op: {node.op}")
        return code
    raise Exception(f"Unhandled expr: {node}")

def add_const(consts: List[Any], v: Any) -> int:
    consts.append(v)
    return len(consts) - 1