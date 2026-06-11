# axon/vm.py
"""
Stack-based virtual machine for the Axon language.

Executes CodeObject instances produced by axon.compiler.

Execution model
---------------
The VM maintains a call stack of Frame objects.  Each Frame represents
one activation record — either the top-level program or a function call.
Frames have their own operand stack and local variable scope; globals are
shared across all frames.

The main run loop fetches one instruction at a time, dispatches on the
opcode string, and manipulates the current frame's stack and/or globals.

Jump instructions use *absolute* instruction indices (matching what the
compiler emits), so there are no offset calculations in the VM.

Supported opcodes
-----------------
  LOAD_CONST   idx          push consts[idx]
  LOAD_NAME    name         push variable (locals first, then globals)
  STORE_NAME   name         pop → store in locals
  POP                       discard top of stack

  BINARY_ADD / SUB / MUL / DIV / MOD
  BINARY_EQ / NE / LT / LE / GT / GE
  BINARY_AND / BINARY_OR    (eager — both sides already on stack)
  UNARY_NEG / UNARY_NOT

  BUILD_LIST   n            pop n items → push list
  BUILD_DICT   n            pop 2n items (interleaved k,v) → push dict
  BINARY_SUBSCR             pop idx, pop collection → push item

  JUMP         target       set ip = target
  JUMP_IF_FALSE target      pop; if falsy set ip = target
  JUMP_IF_TRUE  target      pop; if truthy set ip = target

  MAKE_FUNCTION name params co_idx
                            create AxonFunction, store in globals
  CALL_FUNCTION name argc   pop argc args, call (host or Axon), push result
  RETURN                    pop return value, restore caller frame

  PRINT                     pop and print  (legacy / built-in shortcut)
  CLEAR                     clear terminal
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from axon.compiler import CodeObject


# ---------------------------------------------------------------------------
# RuntimeError subclass so we can attach location info later
# ---------------------------------------------------------------------------

class AxonRuntimeError(Exception):
    pass


# ---------------------------------------------------------------------------
# AxonFunction  — first-class function value
# ---------------------------------------------------------------------------

@dataclass
class AxonFunction:
    """
    Represents a user-defined Axon function at runtime.

    name    : function name (for error messages / repr)
    params  : tuple of parameter name strings
    code    : compiled body CodeObject
    closure : the global env snapshot at definition time (future use)
    """
    name:   str
    params: Tuple[str, ...]
    code:   CodeObject

    def __repr__(self) -> str:
        return f"<fn {self.name}({', '.join(self.params)})>"


# ---------------------------------------------------------------------------
# Frame  — one activation record on the call stack
# ---------------------------------------------------------------------------

@dataclass
class Frame:
    """
    A single execution context.

    code    : the instruction list being executed
    consts  : constant pool for this chunk
    locals  : local variable scope (separate per call)
    stack   : operand stack
    ip      : instruction pointer (index into code)
    name    : human-readable label for tracebacks
    """
    code:   List[Tuple]
    consts: List[Any]
    locals: Dict[str, Any]
    name:   str
    stack:  List[Any]        = field(default_factory=list)
    ip:     int              = 0

    # -- stack helpers --

    def push(self, value: Any) -> None:
        self.stack.append(value)

    def pop(self) -> Any:
        if not self.stack:
            raise AxonRuntimeError(f"Stack underflow in '{self.name}'")
        return self.stack.pop()

    def peek(self) -> Any:
        if not self.stack:
            raise AxonRuntimeError(f"Stack underflow in '{self.name}'")
        return self.stack[-1]


# ---------------------------------------------------------------------------
# Built-in functions
# ---------------------------------------------------------------------------

def _builtin_print(*args) -> None:
    print(*args)
    return None

def _builtin_len(obj) -> int:
    try:
        return len(obj)
    except TypeError:
        raise AxonRuntimeError(f"len() does not support type '{type(obj).__name__}'")

def _builtin_type(obj) -> str:
    return type(obj).__name__

def _builtin_int(obj) -> int:
    try:
        return int(obj)
    except (ValueError, TypeError):
        raise AxonRuntimeError(f"Cannot convert {obj!r} to int")

def _builtin_float(obj) -> float:
    try:
        return float(obj)
    except (ValueError, TypeError):
        raise AxonRuntimeError(f"Cannot convert {obj!r} to float")

def _builtin_str(obj) -> str:
    return str(obj)

def _builtin_bool(obj) -> bool:
    return bool(obj)

def _builtin_range(*args) -> list:
    try:
        return list(range(*[int(a) for a in args]))
    except TypeError as e:
        raise AxonRuntimeError(f"range() error: {e}")

def _builtin_append(lst, item) -> None:
    if not isinstance(lst, list):
        raise AxonRuntimeError("append() expects a list as first argument")
    lst.append(item)
    return None

def _builtin_pop(lst) -> Any:
    if not isinstance(lst, list):
        raise AxonRuntimeError("pop() expects a list")
    if not lst:
        raise AxonRuntimeError("pop() on empty list")
    return lst.pop()

def _builtin_keys(d) -> list:
    if not isinstance(d, dict):
        raise AxonRuntimeError("keys() expects a dict")
    return list(d.keys())

def _builtin_values(d) -> list:
    if not isinstance(d, dict):
        raise AxonRuntimeError("values() expects a dict")
    return list(d.values())


BUILTINS: Dict[str, Any] = {
    "print":  _builtin_print,
    "len":    _builtin_len,
    "type":   _builtin_type,
    "int":    _builtin_int,
    "float":  _builtin_float,
    "str":    _builtin_str,
    "bool":   _builtin_bool,
    "range":  _builtin_range,
    "append": _builtin_append,
    "pop":    _builtin_pop,
    "keys":   _builtin_keys,
    "values": _builtin_values,
}


# ---------------------------------------------------------------------------
# VM
# ---------------------------------------------------------------------------

class VM:
    """
    Stack-based bytecode interpreter for Axon.

    Usage:
        vm = VM()
        vm.execute(code_object)
    """

    def __init__(self):
        # Globals: shared across all frames, seeded with built-ins
        self.globals: Dict[str, Any] = dict(BUILTINS)
        # Call stack
        self._frames: List[Frame] = []

    # ------------------------------------------------------------------
    # Frame management
    # ------------------------------------------------------------------

    def _push_frame(
        self,
        co: CodeObject,
        local_vars: Optional[Dict[str, Any]] = None,
    ) -> Frame:
        frame = Frame(
            code=co.code,
            consts=co.consts,
            locals=local_vars or {},
            name=co.name,
        )
        self._frames.append(frame)
        return frame

    def _pop_frame(self) -> Frame:
        return self._frames.pop()

    def _current_frame(self) -> Frame:
        return self._frames[-1]

    # ------------------------------------------------------------------
    # Variable lookup: locals shadow globals
    # ------------------------------------------------------------------

    def _load(self, name: str, frame: Frame) -> Any:
        if name in frame.locals:
            return frame.locals[name]
        if name in self.globals:
            return self.globals[name]
        raise AxonRuntimeError(f"NameError: '{name}' is not defined")

    def _store(self, name: str, value: Any, frame: Frame) -> None:
        # If the name already exists in locals, update locals.
        # If it exists in globals but not locals, update globals.
        # Otherwise create it in locals (new declaration).
        if name in frame.locals:
            frame.locals[name] = value
        elif name in self.globals and not callable(self.globals[name]):
            self.globals[name] = value
        else:
            frame.locals[name] = value

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def execute(self, co: CodeObject) -> Any:
        """
        Execute a top-level CodeObject.
        Returns the return value if the code ends with RETURN, else None.
        """
        self._push_frame(co)
        return self._run()

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    def _run(self) -> Any:
        while self._frames:
            frame = self._current_frame()

            # Frame finished normally
            if frame.ip >= len(frame.code):
                self._pop_frame()
                continue

            instr = frame.code[frame.ip]
            frame.ip += 1
            op = instr[0]

            # -- Constants & names --------------------------------------

            if op == "LOAD_CONST":
                frame.push(frame.consts[instr[1]])

            elif op == "LOAD_NAME":
                frame.push(self._load(instr[1], frame))

            elif op == "STORE_NAME":
                self._store(instr[1], frame.pop(), frame)

            elif op == "POP":
                frame.pop()

            # -- Arithmetic ---------------------------------------------

            elif op == "BINARY_ADD":
                r, l = frame.pop(), frame.pop()
                frame.push(l + r)

            elif op == "BINARY_SUB":
                r, l = frame.pop(), frame.pop()
                frame.push(l - r)

            elif op == "BINARY_MUL":
                r, l = frame.pop(), frame.pop()
                frame.push(l * r)

            elif op == "BINARY_DIV":
                r, l = frame.pop(), frame.pop()
                if r == 0:
                    raise AxonRuntimeError("ZeroDivisionError: division by zero")
                frame.push(l / r)

            elif op == "BINARY_MOD":
                r, l = frame.pop(), frame.pop()
                if r == 0:
                    raise AxonRuntimeError("ZeroDivisionError: modulo by zero")
                frame.push(l % r)

            # -- Comparison ---------------------------------------------

            elif op == "BINARY_EQ":
                r, l = frame.pop(), frame.pop()
                frame.push(l == r)

            elif op == "BINARY_NE":
                r, l = frame.pop(), frame.pop()
                frame.push(l != r)

            elif op == "BINARY_LT":
                r, l = frame.pop(), frame.pop()
                frame.push(l < r)

            elif op == "BINARY_LE":
                r, l = frame.pop(), frame.pop()
                frame.push(l <= r)

            elif op == "BINARY_GT":
                r, l = frame.pop(), frame.pop()
                frame.push(l > r)

            elif op == "BINARY_GE":
                r, l = frame.pop(), frame.pop()
                frame.push(l >= r)

            # -- Logical ------------------------------------------------

            elif op == "BINARY_AND":
                r, l = frame.pop(), frame.pop()
                frame.push(l and r)

            elif op == "BINARY_OR":
                r, l = frame.pop(), frame.pop()
                frame.push(l or r)

            elif op == "UNARY_NEG":
                frame.push(-frame.pop())

            elif op == "UNARY_NOT":
                frame.push(not frame.pop())

            # -- Collections --------------------------------------------

            elif op == "BUILD_LIST":
                n     = instr[1]
                items = [frame.pop() for _ in range(n)]
                frame.push(list(reversed(items)))

            elif op == "BUILD_DICT":
                n = instr[1]
                d = {}
                # pairs were pushed k, v, k, v ... pop in reverse
                pairs = [frame.pop() for _ in range(n * 2)]
                pairs.reverse()
                for i in range(0, len(pairs), 2):
                    d[pairs[i]] = pairs[i + 1]
                frame.push(d)

            elif op == "BINARY_SUBSCR":
                idx  = frame.pop()
                coll = frame.pop()
                try:
                    frame.push(coll[idx])
                except (KeyError, IndexError) as e:
                    raise AxonRuntimeError(f"IndexError: {e}")
                except TypeError as e:
                    raise AxonRuntimeError(f"TypeError: {e}")

            # -- Control flow -------------------------------------------

            elif op == "JUMP":
                frame.ip = instr[1]

            elif op == "JUMP_IF_FALSE":
                if not frame.pop():
                    frame.ip = instr[1]

            elif op == "JUMP_IF_TRUE":
                if frame.pop():
                    frame.ip = instr[1]

            # -- Functions ----------------------------------------------

            elif op == "MAKE_FUNCTION":
                name, params, co_idx = instr[1], instr[2], instr[3]
                body_co = frame.consts[co_idx]
                fn = AxonFunction(name=name, params=params, code=body_co)
                # Functions are always stored as globals so they're callable
                # from any scope
                self.globals[name] = fn

            elif op == "CALL_FUNCTION":
                name, argc = instr[1], instr[2]
                args = list(reversed([frame.pop() for _ in range(argc)]))

                func = self._load(name, frame)

                # Host (Python) callable — built-ins
                if callable(func) and not isinstance(func, AxonFunction):
                    try:
                        result = func(*args)
                    except AxonRuntimeError:
                        raise
                    except Exception as e:
                        raise AxonRuntimeError(
                            f"Error in built-in '{name}': {e}"
                        )
                    frame.push(result)

                # User-defined Axon function
                elif isinstance(func, AxonFunction):
                    if len(args) != len(func.params):
                        raise AxonRuntimeError(
                            f"TypeError: '{name}' takes {len(func.params)} "
                            f"argument(s) but {len(args)} were given"
                        )
                    # Build local scope from params + args
                    local_vars = dict(zip(func.params, args))
                    # Push a new frame; save a sentinel on the *caller's*
                    # stack so we know where to put the return value
                    frame.push(_RETURN_SENTINEL)
                    self._push_frame(func.code, local_vars)

                else:
                    raise AxonRuntimeError(f"TypeError: '{name}' is not callable")

            elif op == "RETURN":
                ret_val = frame.pop()
                self._pop_frame()          # leave the function frame

                if self._frames:
                    caller = self._current_frame()
                    # Pop the sentinel we left before the call
                    if caller.stack and caller.peek() is _RETURN_SENTINEL:
                        caller.pop()
                    caller.push(ret_val)   # deliver return value to caller

            # -- Built-in shortcuts -------------------------------------

            elif op == "PRINT":
                print(frame.pop())

            elif op == "CLEAR":
                os.system("cls" if os.name == "nt" else "clear")

            # -- Unknown ------------------------------------------------

            else:
                raise AxonRuntimeError(f"Unknown opcode '{op}'")

        return None


# Sentinel object used to mark the stack position where a return value
# should land after a function call.
_RETURN_SENTINEL = object()