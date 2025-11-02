# vm.py (skeletal)
from dataclasses import dataclass
from typing import List, Any, Dict, Tuple

@dataclass
class Frame:
    code: List[Tuple]
    ip: int
    stack: List[Any]
    locals: Dict[str, Any]
    name: str

class VM:
    def __init__(self):
        self.frames: List[Frame] = []
        self.globals: Dict[str, Any] = {}
        self.consts: List[Any] = []

    def push_frame(self, code, name="<module>"):
        f = Frame(code=code, ip=0, stack=[], locals={}, name=name)
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

            if op == 'CONST':
                f.stack.append(self.consts[instr[1]])
            elif op == 'LOAD_NAME':
                name = instr[1]
                val = f.locals.get(name, self.globals.get(name))
                if val is None:
                    raise RuntimeError(f"NameError: {name}")
                f.stack.append(val)
            elif op == 'STORE_NAME':
                name = instr[1]
                val = f.stack.pop()
                f.locals[name] = val
            elif op == 'BINARY_ADD':
                b = f.stack.pop(); a = f.stack.pop()
                f.stack.append(a + b)
            elif op == 'PRINT':
                val = f.stack.pop()
                print(val)
            elif op == 'RETURN':
                ret = f.stack.pop() if f.stack else None
                self.pop_frame()
                if self.frames:
                    self.current().stack.append(ret)
            else:
                raise RuntimeError(f"Unknown opcode {op}")
