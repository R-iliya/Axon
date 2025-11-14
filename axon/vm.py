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
        self.globals["print"] = self._host_print

    def push_frame(self, co: CodeObject):
        f = Frame(code=co.code.copy(), ip=0, stack=[], locals={}, name=co.name, consts=co.consts.copy(), loop_stack=[])
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

            elif op.startswith("BINARY_"):
                b = f.stack.pop(); a = f.stack.pop()
                if op == "BINARY_ADD": f.stack.append(a + b)
                elif op == "BINARY_SUB": f.stack.append(a - b)
                elif op == "BINARY_MUL": f.stack.append(a * b)
                elif op == "BINARY_DIV": f.stack.append(a / b)

            elif op == "PRINT":
                val = f.stack.pop()
                printer = self.globals.get("print", builtins.print)
                printer(val)

            elif op == "CLEAR":
                os.system("cls" if os.name == "nt" else "clear")

            elif op == "JUMP":
                offset = instr[1]
                f.ip += offset - 1

            elif op == "JUMP_IF_FALSE":
                offset = instr[1]
                cond = f.stack.pop()
                if not cond:
                    f.ip += offset - 1

            elif op == "BREAK":
                if not f.loop_stack:
                    raise RuntimeError("BREAK outside loop")
                f.ip = f.loop_stack[-1]
                continue

            elif op == "CONTINUE":
                if not f.loop_stack:
                    raise RuntimeError("CONTINUE outside loop")
                f.ip = f.loop_stack[-1] - 1
                continue

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

            elif op == "RETURN":
                if f.stack:
                    f.return_value = f.stack.pop()
                self.pop_frame()
            elif op == "FOR_LOOP":
                var_name, end_idx, body_code = instr[1], instr[2], instr[3]
                end_val = f.consts[end_idx]
                start_val = f.locals.get(var_name, 0)
                for i in range(start_val, end_val):
                    f.locals[var_name] = i
                    body_vm = VM()
                    body_vm.globals = self.globals
                    body_vm.push_frame(CodeObject(body_code, f.consts, name=f"{f.name}.{var_name}"))
                    body_vm.run()
            else:
                raise RuntimeError(f"Unknown opcode {op}")

    @staticmethod
    def _host_print(v):
        print(v)
