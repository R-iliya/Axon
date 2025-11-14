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
        # globals persist across top-level frames / REPL runs
        self.globals: Dict[str, Any] = {}
        # register basic host bindings
        self.globals["print"] = self._host_print

    def push_frame(self, co: CodeObject):
        # Top-level frames (program entry / REPL) should persist variables.
        # Make top-level frames share self.globals as locals so `let` survives.
        if co.name == "__main__":
            locals_ref = self.globals
        else:
            locals_ref = {}
        f = Frame(
            code=co.code.copy(),
            ip=0,
            stack=[],
            locals=locals_ref,
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
            # if we've exhausted code, pop frame
            if f.ip >= len(f.code):
                self.pop_frame()
                continue

            instr = f.code[f.ip]
            f.ip += 1
            op = instr[0]

            # ---------- stack / consts ----------
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
                if not f.stack:
                    raise RuntimeError("STORE_NAME with empty stack")
                val = f.stack.pop()
                # store into locals (which may be shared globals for top-level)
                f.locals[name] = val

            # ---------- arithmetic / binary ----------
            elif op == "BINARY_ADD":
                b = f.stack.pop(); a = f.stack.pop(); f.stack.append(a + b)
            elif op == "BINARY_SUB":
                b = f.stack.pop(); a = f.stack.pop(); f.stack.append(a - b)
            elif op == "BINARY_MUL":
                b = f.stack.pop(); a = f.stack.pop(); f.stack.append(a * b)
            elif op == "BINARY_DIV":
                b = f.stack.pop(); a = f.stack.pop(); f.stack.append(a / b)
            elif op == "BINARY_MOD":
                b = f.stack.pop(); a = f.stack.pop(); f.stack.append(a % b)

            # boolean-like binary ops (note: 'and'/'or' in compiler are mapped here)
            elif op == "BINARY_AND":
                b = f.stack.pop(); a = f.stack.pop(); f.stack.append(a and b)
            elif op == "BINARY_OR":
                b = f.stack.pop(); a = f.stack.pop(); f.stack.append(a or b)

            # comparisons
            elif op == "COMPARE_EQ":
                b = f.stack.pop(); a = f.stack.pop(); f.stack.append(a == b)
            elif op == "COMPARE_NE":
                b = f.stack.pop(); a = f.stack.pop(); f.stack.append(a != b)
            elif op == "COMPARE_LT":
                b = f.stack.pop(); a = f.stack.pop(); f.stack.append(a < b)
            elif op == "COMPARE_LE":
                b = f.stack.pop(); a = f.stack.pop(); f.stack.append(a <= b)
            elif op == "COMPARE_GT":
                b = f.stack.pop(); a = f.stack.pop(); f.stack.append(a > b)
            elif op == "COMPARE_GE":
                b = f.stack.pop(); a = f.stack.pop(); f.stack.append(a >= b)

            # unary
            elif op == "UNARY_NEG":
                a = f.stack.pop(); f.stack.append(-a)
            elif op == "UNARY_NOT":
                a = f.stack.pop(); f.stack.append(not a)

            # ---------- build containers ----------
            elif op == "BUILD_LIST":
                n = instr[1]
                if n:
                    items = [f.stack.pop() for _ in range(n)][::-1]
                else:
                    items = []
                f.stack.append(items)

            elif op == "BUILD_DICT":
                n = instr[1]
                d = {}
                for _ in range(n):
                    val = f.stack.pop()
                    key = f.stack.pop()
                    d[key] = val
                f.stack.append(d)

            elif op == "BINARY_SUBSCR":
                idx = f.stack.pop()
                coll = f.stack.pop()
                f.stack.append(coll[idx])

            # ---------- control / flow ----------
            elif op == "PRINT":
                # Print consumes top of stack (if any); otherwise prints None
                val = f.stack.pop() if f.stack else None
                printer = self.globals.get("print", builtins.print)
                # call host print (our wrapper) or fallback builtin
                if callable(printer):
                    try:
                        printer(val)
                    except TypeError:
                        # if host wrapper expects different signature, fallback
                        print(val)
                else:
                    print(val)

            elif op == "CLEAR":
                os.system("cls" if os.name == "nt" else "clear")

            elif op == "JUMP":
                offset = instr[1]
                # offset is relative (number of instructions to advance), adjust because we've incremented ip
                f.ip += offset - 1

            elif op == "JUMP_IF_FALSE":
                offset = instr[1]
                cond = f.stack.pop() if f.stack else False
                if not cond:
                    f.ip += offset - 1

            elif op == "BREAK":
                if not f.loop_stack:
                    raise RuntimeError("BREAK outside loop")
                # jump to after loop: loop_stack stores exit ip
                exit_ip = f.loop_stack[-1]
                f.ip = exit_ip

            elif op == "CONTINUE":
                if not f.loop_stack:
                    raise RuntimeError("CONTINUE outside loop")
                # jump back to loop condition (we expect the compiler to set the loop start properly)
                start_ip = f.loop_stack[-2] if len(f.loop_stack) >= 2 else f.loop_stack[-1]
                f.ip = start_ip

            # ---------- functions ----------
            elif op == "MAKE_FUNCTION":
                # MAKE_FUNCTION (name, params, func_code, [optional func_consts])
                name = instr[1]
                params = instr[2]
                func_code = instr[3]
                func_consts = instr[4] if len(instr) > 4 else f.consts.copy()
                # store function representation in locals (or globals for top-level)
                f.locals[name] = (params, func_code, func_consts)

            elif op == "CALL_FUNCTION":
                name = instr[1]
                argc = instr[2]
                args = [f.stack.pop() for _ in range(argc)][::-1]
                func = f.locals.get(name) or self.globals.get(name)
                if func is None:
                    raise RuntimeError(f"NameError: function '{name}' is not defined")
                # if func is a python callable host binding
                if callable(func) and not isinstance(func, tuple):
                    # call host function directly and push return to stack
                    ret = func(*args)
                    f.stack.append(ret)
                else:
                    # user-defined function tuple: (params, func_code, func_consts)
                    params, func_code, func_consts = func if len(func) == 3 else (func[0], func[1], f.consts)
                    new_co = CodeObject(func_code, func_consts, name=name)
                    # push frame for function call; function frames get their own locals
                    self.push_frame(new_co)
                    new_frame = self.current()
                    # set function arguments as locals
                    for p, a in zip(params, args):
                        new_frame.locals[p] = a

            elif op == "RETURN":
                # optional return value is on stack
                if f.stack:
                    f.return_value = f.stack.pop()
                else:
                    f.return_value = None
                self.pop_frame()

            elif op == "FOR_LOOP":
                # (var_name, end_idx, body_code)
                var_name = instr[1]
                end_idx = instr[2]
                body_code = instr[3]
                end_val = f.consts[end_idx]
                # Start value should already be in f.locals (compiler stores it prior)
                start_val = f.locals.get(var_name, 0)
                # We'll execute the body for each iteration in a child frame
                for i in range(start_val, end_val):
                    f.locals[var_name] = i
                    # run body in a child frame that shares top-level globals (so nested lets persist sensibly)
                    body_co = CodeObject(body_code, f.consts.copy(), name=f"{f.name}.for")
                    # child vm reuses same globals
                    child_vm = VM()
                    child_vm.globals = self.globals
                    child_vm.push_frame(body_co)
                    child_vm.run()
                # after loop, continue

            else:
                raise RuntimeError(f"Unknown opcode {op}")

    @staticmethod
    def _host_print(v):
        print(v)
