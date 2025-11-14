from dataclasses import dataclass
from typing import List, Any, Dict, Tuple
from axon.compiler import CodeObject
import builtins, os

@dataclass
class Frame:
    code: List[Tuple]
    ip: int
    stack: List[Any]
    consts: List[Any]
    name: str
    return_value: Any = None
    loop_stack: List[int] = None

class VM:
    def __init__(self):
        self.frames: List[Frame] = []
        self.globals: Dict[str, Any] = {
            "print": self._host_print
        }

    # ---------------- FRAME MGMT ----------------
    def push_frame(self, co: CodeObject):
        f = Frame(
            code=co.code.copy(),
            ip=0,
            stack=[],
            consts=co.consts.copy(),
            name=co.name,
            loop_stack=[]
        )
        self.frames.append(f)

    def pop_frame(self):
        return self.frames.pop()

    def current(self) -> Frame:
        return self.frames[-1]

    # ---------------- VM RUN LOOP ----------------
    def run(self):
        while self.frames:
            f = self.current()

            if f.ip >= len(f.code):
                self.pop_frame()
                continue

            instr = f.code[f.ip]
            f.ip += 1
            op = instr[0]

            # ----- CONSTANTS -----
            if op == "CONST":
                f.stack.append(f.consts[instr[1]])

            # ----- VARIABLES -----
            elif op == "LOAD_NAME":
                name = instr[1]
                if name in self.globals:
                    f.stack.append(self.globals[name])
                else:
                    raise RuntimeError(f"NameError: name '{name}' is not defined")

            elif op == "STORE_NAME":
                name = instr[1]
                self.globals[name] = f.stack.pop()

            # ----- BINARY OPS -----
            elif op == "BINARY_ADD":
                b, a = f.stack.pop(), f.stack.pop()
                f.stack.append(a + b)

            elif op == "BINARY_SUB":
                b, a = f.stack.pop(), f.stack.pop()
                f.stack.append(a - b)

            elif op == "BINARY_MUL":
                b, a = f.stack.pop(), f.stack.pop()
                f.stack.append(a * b)

            elif op == "BINARY_DIV":
                b, a = f.stack.pop(), f.stack.pop()
                f.stack.append(a / b)

            elif op == "BINARY_MOD":
                b, a = f.stack.pop(), f.stack.pop()
                f.stack.append(a % b)

            # ----- COMPARES -----
            elif op == "COMPARE_EQ":
                b, a = f.stack.pop(), f.stack.pop()
                f.stack.append(a == b)

            elif op == "COMPARE_NE":
                b, a = f.stack.pop(), f.stack.pop()
                f.stack.append(a != b)

            elif op == "COMPARE_LT":
                b, a = f.stack.pop(), f.stack.pop()
                f.stack.append(a < b)

            elif op == "COMPARE_LE":
                b, a = f.stack.pop(), f.stack.pop()
                f.stack.append(a <= b)

            elif op == "COMPARE_GT":
                b, a = f.stack.pop(), f.stack.pop()
                f.stack.append(a > b)

            elif op == "COMPARE_GE":
                b, a = f.stack.pop(), f.stack.pop()
                f.stack.append(a >= b)

            # ----- LOGICAL OPS -----
            elif op == "BINARY_AND":
                b, a = f.stack.pop(), f.stack.pop()
                f.stack.append(a and b)

            elif op == "BINARY_OR":
                b, a = f.stack.pop(), f.stack.pop()
                f.stack.append(a or b)

            # ----- UNARY -----
            elif op == "UNARY_NEG":
                f.stack.append(-f.stack.pop())

            elif op == "UNARY_NOT":
                f.stack.append(not f.stack.pop())

            # ----- LIST / DICT -----
            elif op == "BUILD_LIST":
                n = instr[1]
                items = [f.stack.pop() for _ in range(n)][::-1]
                f.stack.append(items)

            elif op == "BUILD_DICT":
                n = instr[1]
                d = {}
                for _ in range(n):
                    v = f.stack.pop()
                    k = f.stack.pop()
                    d[k] = v
                f.stack.append(d)

            elif op == "BINARY_SUBSCR":
                idx = f.stack.pop()
                coll = f.stack.pop()
                f.stack.append(coll[idx])

            # ----- PRINT -----
            elif op == "PRINT":
                val = f.stack.pop()
                self.globals["print"](val)

            # ----- CLEAR -----
            elif op == "CLEAR":
                os.system("cls" if os.name == "nt" else "clear")

            # ----- JUMPS -----
            elif op == "JUMP":
                f.ip += instr[1] - 1

            elif op == "JUMP_IF_FALSE":
                offset = instr[1]
                cond = f.stack.pop() if f.stack else False
                if not cond:
                    f.ip += offset - 1

            # ----- LOOP FLOW -----
            elif op == "BREAK":
                f.ip = f.loop_stack[-1]

            elif op == "CONTINUE":
                f.ip = f.loop_stack[-1] - 1

            # ----- FUNCTION -----
            elif op == "MAKE_FUNCTION":
                name, params, func_code = instr[1:]
                self.globals[name] = (params, func_code)

            elif op == "CALL_FUNCTION":
                name, argc = instr[1:]
                args = [f.stack.pop() for _ in range(argc)][::-1]
                func = self.globals.get(name)

                # host function
                if callable(func):
                    f.stack.append(func(*args))

                # user function
                else:
                    params, body_code = func
                    new_co = CodeObject(body_code, f.consts, name=name)
                    self.push_frame(new_co)
                    newf = self.current()
                    for p, a in zip(params, args):
                        self.globals[p] = a

            elif op == "RETURN":
                if f.stack:
                    f.return_value = f.stack.pop()
                self.pop_frame()

            elif op == "POP_TOP":
                if f.stack:
                    f.stack.pop()

            else:
                raise RuntimeError(f"Unknown opcode {op}")

    @staticmethod
    def _host_print(v):
        print(v)
