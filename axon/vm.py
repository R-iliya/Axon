# axon/vm.py
from dataclasses import dataclass
from typing import List, Any, Dict, Tuple
from axon.compiler import CodeObject
import builtins

@dataclass
class Frame:
    code: List[Tuple]
    ip: int
    stack: List[Any]
    locals: Dict[str, Any]
    name: str
    consts: List[Any]

class VM:
    def __init__(self):
        self.frames: List[Frame] = []
        self.globals: Dict[str, Any] = {}
        # register basic host bindings
        self.globals["print"] = self._host_print

    def push_frame(self, co: CodeObject):
        f = Frame(code=co.code.copy(), ip=0, stack=[], locals={}, name=co.name, consts=co.consts.copy())
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
                idx = instr[1]
                f.stack.append(f.consts[idx])
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
            elif op == "BINARY_ADD":
                b = f.stack.pop(); a = f.stack.pop()
                f.stack.append(a + b)
            elif op == "BINARY_SUB":
                b = f.stack.pop(); a = f.stack.pop()
                f.stack.append(a - b)
            elif op == "BINARY_MUL":
                b = f.stack.pop(); a = f.stack.pop()
                f.stack.append(a * b)
            elif op == "BINARY_DIV":
                b = f.stack.pop(); a = f.stack.pop()
                f.stack.append(a / b)
            elif op == "PRINT":
                val = f.stack.pop()
                # call print host if available, else builtin print
                printer = self.globals.get("print", builtins.print)
                # printer might be host wrapper expecting args
                if callable(printer):
                    printer(val)
                else:
                    print(val)
            elif op == "RETURN":
                # pop frame and optionally push return value (none here)
                self.pop_frame()
            else:
                raise RuntimeError(f"Unknown opcode {op}")
    # simple host binding
    def _host_print(self, v):
        print(v)
