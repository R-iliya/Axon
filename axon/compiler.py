# axon/compiler.py
from typing import List, Tuple, Any
from dataclasses import dataclass
from axon.nodes import *

Instruction = Tuple

@dataclass
class CodeObject:
    code: List[Instruction]
    consts: List[Any]
    name: str

def compile_program(prog) -> CodeObject:
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
            code.append(("CONST", add_const(consts, None)))  # push None after printing

        # clear screen
        elif isinstance(stmt, ClearNode):
            code.append(("CLEAR",))

        # if/else
        elif isinstance(stmt, IfNode):
            # compile condition
            code.extend(compile_expr(stmt.condition, consts))

            # compile true and false branches
            true_code = compile_program(stmt.body).code
            false_code = compile_program(stmt.else_body).code if stmt.else_body else []

            # jump over true body if condition is false
            code.append(("JUMP_IF_FALSE", len(true_code) + (1 if false_code else 0)))

            # insert true branch
            code.extend(true_code)

            if false_code:
                # jump past false branch after true executes
                code.append(("JUMP", len(false_code)))
                code.extend(false_code)

            # normalize stack: push None so REPL doesn’t print leftover values
            code.append(("CONST", add_const(consts, None)))

        # while loop
        elif isinstance(stmt, WhileNode):
            start_idx = len(code)
            code.extend(compile_expr(stmt.condition, consts))
            body_code = compile_program(stmt.body).code
            code.append(("JUMP_IF_FALSE", len(body_code) + 1))
            code.extend(body_code)
            code.append(("JUMP", -(len(body_code) + 2)))  # jump back to condition

        # for loop
        elif isinstance(stmt, ForNode):
            code.extend(compile_expr(stmt.start_expr, consts))
            code.append(("STORE_NAME", stmt.var_name))
            end_idx = add_const(consts, stmt.end_expr.eval({}))
            body_code = compile_program(stmt.body).code
            code.append(("FOR_LOOP", stmt.var_name, end_idx, body_code))

        # break
        elif isinstance(stmt, BreakNode):
            code.append(("BREAK",))

        # continue
        elif isinstance(stmt, ContinueNode):
            code.append(("CONTINUE",))

        # function definition
        elif isinstance(stmt, FunctionNode):
            func_code = compile_program(stmt.body).code
            code.append(("MAKE_FUNCTION", stmt.name, stmt.params, func_code))

        # function call
        elif isinstance(stmt, CallNode):
            for arg in stmt.args:
                code.extend(compile_expr(arg, consts))
            code.append(("CALL_FUNCTION", stmt.name, len(stmt.args)))

        # return
        elif isinstance(stmt, ReturnNode):
            code.extend(compile_expr(stmt.expr, consts))
            code.append(("RETURN",))

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
        op_map = {
            "+": "BINARY_ADD",
            "-": "BINARY_SUB",
            "*": "BINARY_MUL",
            "/": "BINARY_DIV",
            "%": "BINARY_MOD",
            "==": "COMPARE_EQ",
            "!=": "COMPARE_NE",
            "<": "COMPARE_LT",
            "<=": "COMPARE_LE",
            ">": "COMPARE_GT",
            ">=": "COMPARE_GE",
            "and": "BINARY_AND",
            "or": "BINARY_OR",
        }
        if node.op not in op_map:
            raise Exception(f"Unknown binary op: {node.op}")
        code.append((op_map[node.op],))
        return code

    # unary operators
    if isinstance(node, UnaryOpNode):
        code = compile_expr(node.expr, consts)
        op_map = {"-": "UNARY_NEG", "not": "UNARY_NOT"}
        if node.op not in op_map:
            raise Exception(f"Unknown unary op: {node.op}")
        code.append((op_map[node.op],))
        return code

    # list literal
    if isinstance(node, ListNode):
        code = []
        for elem in node.elements:
            code.extend(compile_expr(elem, consts))
        code.append(("BUILD_LIST", len(node.elements)))
        return code

    # dict literal
    if isinstance(node, DictNode):
        code = []
        for k, v in node.entries:
            code.extend(compile_expr(k, consts))
            code.extend(compile_expr(v, consts))
        code.append(("BUILD_DICT", len(node.entries)))
        return code

    # index access
    if isinstance(node, IndexNode):
        code = compile_expr(node.collection, consts)
        code.extend(compile_expr(node.index, consts))
        code.append(("BINARY_SUBSCR",))
        return code

    raise Exception(f"Unhandled expr: {node}")


def add_const(consts: List[Any], v: Any) -> int:
    consts.append(v)
    return len(consts) - 1
