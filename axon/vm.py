# axon/vm.py
from dataclasses import dataclass
from typing import List, Any, Dict, Tuple
from axon.compiler import CodeObject
import builtins, os

@dataclass
class Frame:
    code: List[Tuple]
    ip: int
    stack: List[Any]
    locals: Dict[str, Any]
    name: str
    consts: List[Any]
    loop_stack: List[int] = None
    return_value: Any = None

class VM:
    def __init__(self):
        self.frames: List[Frame] = []
        self.globals: Dict[str, Any] = {}
        # persistent host bindings
        self.globals["print"] = self._host_print
        self.globals["cls"] = self._host_cls

    def push_frame(self, co: CodeObject):
        f = Frame(
            code=co.code.copy(),
            ip=0,
            stack=[],
            locals={},
            name=co.name,
            consts=co.consts.copy(),
            loop_stack=[]
        )
        self.frames.append(f)

    def pop_frame(self):
        return self.frames.pop()

    def current(self) -> Frame:
        return self.frames[-1]

    def run(self):
        while self.frames:
            f = self.current()
            if f.ip >= len(f.code):
                self.pop_frame()
                continue

            instr = f.code[f.ip]
            f.ip += 1
            op = instr[0]

            # -----------------------
            # Stack operations / constants
            # -----------------------
            if op == "CONST":
                f.stack.append(f.consts[instr[1]])
            elif op == "LOAD_NAME":
                name = instr[1]
                if name in f.locals:
                    f.stack.append(f.locals[name])
                elif name in self.globals:
                    f.stack.append(self.globals[name])
                else:
                    raise RuntimeError(f"NameError: name '{name}' is not defined")
            elif op == "STORE_NAME":
                name = instr[1]
                val = f.stack.pop()
                f.locals[name] = val

            # -----------------------
            # Binary ops
            # -----------------------
            elif op.startswith("BINARY_"):
                b = f.stack.pop()
                a = f.stack.pop()
                if op == "BINARY_ADD": f.stack.append(a + b)
                elif op == "BINARY_SUB": f.stack.append(a - b)
                elif op == "BINARY_MUL": f.stack.append(a * b)
                elif op == "BINARY_DIV": f.stack.append(a / b)
                elif op == "BINARY_EQ": f.stack.append(a == b)
                elif op == "BINARY_NE": f.stack.append(a != b)
                elif op == "BINARY_LT": f.stack.append(a < b)
                elif op == "BINARY_GT": f.stack.append(a > b)
                elif op == "BINARY_LTE": f.stack.append(a <= b)
                elif op == "BINARY_GTE": f.stack.append(a >= b)
                elif op == "BINARY_AND": f.stack.append(a and b)
                elif op == "BINARY_OR": f.stack.append(a or b)

            # -----------------------
            # Unary ops
            # -----------------------
            elif op == "UNARY":
                val = f.stack.pop()
                unary_op = instr[1]
                if unary_op == "-": f.stack.append(-val)
                elif unary_op == "not": f.stack.append(not val)

            # -----------------------
            # List / dict / index
            # -----------------------
            elif op == "BUILD_LIST":
                n = instr[1]
                elems = [f.stack.pop() for _ in range(n)][::-1]
                f.stack.append(elems)
            elif op == "BUILD_DICT":
                n = instr[1]
                items = [f.stack.pop() for _ in range(n*2)][::-1]
                d = {}
                for i in range(0, len(items), 2):
                    d[items[i]] = items[i+1]
                f.stack.append(d)
            elif op == "INDEX":
                idx = f.stack.pop()
                coll = f.stack.pop()
                f.stack.append(coll[idx])

            # -----------------------
            # Printing / clearing
            # -----------------------
            elif op == "PRINT":
                val = f.stack.pop()
                printer = self.globals.get("print", builtins.print)
                printer(val)
            elif op == "CLEAR":
                self._host_cls()

            # -----------------------
            # Flow control
            # -----------------------
            elif op == "JUMP":
                f.ip += instr[1] - 1
            elif op == "JUMP_IF_FALSE":
                cond = f.stack.pop()
                if not cond:
                    f.ip += instr[1] - 1
            elif op == "BREAK":
                if not f.loop_stack:
                    raise RuntimeError("BREAK outside loop")
                f.ip = f.loop_stack[-1]
            elif op == "CONTINUE":
                if not f.loop_stack:
                    raise RuntimeError("CONTINUE outside loop")
                f.ip = f.loop_stack[-1] - 1

            # -----------------------
            # Loops
            # -----------------------
            elif op == "FOR_LOOP":
                var_name, end_val, body_code = instr[1], instr[2], instr[3]
                start_val = f.locals.get(var_name, 0)
                for i in range(start_val, end_val):
                    f.locals[var_name] = i
                    body_vm = VM()
                    body_vm.globals = self.globals
                    body_vm.push_frame(CodeObject(body_code, f.consts, name=f"{f.name}.{var_name}"))
                    body_vm.run()

            # -----------------------
            # Functions
            # -----------------------
            elif op == "MAKE_FUNCTION":
                name, params, func_code = instr[1], instr[2], instr[3]
                f.locals[name] = (params, func_code)
            elif op == "CALL_FUNCTION":
                name, argc = instr[1], instr[2]
                args = [f.stack.pop() for _ in range(argc)][::-1]
                func = f.locals.get(name) or self.globals.get(name)
                if callable(func):
                    f.stack.append(func(*args))
                else:
                    params, func_code = func
                    new_co = CodeObject(func_code, f.consts, name=name)
                    self.push_frame(new_co)
                    new_frame = self.current()
                    for p, a in zip(params, args):
                        new_frame.locals[p] = a

            # -----------------------
            # Return
            # -----------------------
            elif op == "RETURN":
                if f.stack:
                    f.return_value = f.stack.pop()
                self.pop_frame()

            else:
                raise RuntimeError(f"Unknown opcode {op}")

    @staticmethod
    def _host_print(v):
        print(v)

    @staticmethod
    def _host_cls():
        os.system("cls" if os.name == "nt" else "clear")
