# axon/compiler.py
"""
Bytecode compiler for the Axon language.

Walks the AST (axon.nodes) and emits a flat list of instructions
into a CodeObject, which the VM (axon.vm) can execute.

Instruction format
------------------
Every instruction is a tuple:  (opcode, *operands)

Opcodes
-------
  Stack / constants
    LOAD_CONST   idx          push consts[idx]
    LOAD_NAME    name         push value of variable 'name'
    STORE_NAME   name         pop and store into variable 'name'
    POP                       discard top of stack

  Arithmetic / logic (pop two, push result)
    BINARY_ADD
    BINARY_SUB
    BINARY_MUL
    BINARY_DIV
    BINARY_MOD
    BINARY_EQ
    BINARY_NE
    BINARY_LT
    BINARY_LE
    BINARY_GT
    BINARY_GE
    BINARY_AND
    BINARY_OR

  Unary (pop one, push result)
    UNARY_NEG
    UNARY_NOT

  Collections
    BUILD_LIST   n            pop n items → push list
    BUILD_DICT   n            pop 2n items (k,v pairs) → push dict
    BINARY_SUBSCR             pop idx, pop collection → push collection[idx]

  Control flow  (all offsets are *absolute* instruction indices)
    JUMP         target       unconditional jump to target
    JUMP_IF_FALSE target      pop; jump to target if falsy
    JUMP_IF_TRUE  target      pop; jump to target if truthy  (short-circuit or)

  Functions
    MAKE_FUNCTION  name  params_tuple  code_obj
                              create function and store under name
    CALL_FUNCTION  name  argc
                              pop argc args, call function, push result
    RETURN                    pop return value, return to caller

  Built-in
    PRINT                     pop and print value
    CLEAR                     clear the terminal

Absolute jump targets
---------------------
Using absolute indices (not relative offsets) avoids all the off-by-one
bugs that plagued the original compiler. Backpatching is done with a
simple list of (instruction_index, field_index) pairs that get filled in
once the target address is known.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Any, Optional

from axon.nodes import (
    Node,
    NumberLit, StringLit, BoolLit, Var,
    BinOp, UnaryOp, ListLit, DictLit, Index, Call,
    Let, Assign, Print, Clear,
    If, While, For,
    Break, Continue, Return,
    FnDef, ExprStmt,
)


# ---------------------------------------------------------------------------
# CodeObject
# ---------------------------------------------------------------------------

@dataclass
class CodeObject:
    """
    The output of the compiler — everything the VM needs to run a chunk.

    name    : human-readable label (e.g. '__main__' or a function name)
    code    : list of instruction tuples
    consts  : constant pool (numbers, strings, bools, None)
    """
    name:   str
    code:   List[Tuple]  = field(default_factory=list)
    consts: List[Any]    = field(default_factory=list)

    # ------------------------------------------------------------------
    # Helpers used by the compiler
    # ------------------------------------------------------------------

    def add_const(self, value: Any) -> int:
        """Add *value* to the constant pool and return its index."""
        self.consts.append(value)
        return len(self.consts) - 1

    def emit(self, *instr) -> int:
        """Append one instruction tuple and return its index."""
        self.code.append(instr)
        return len(self.code) - 1

    def patch(self, instr_idx: int, field_idx: int, value: Any) -> None:
        """
        Overwrite a single field inside an already-emitted instruction.
        Used for backpatching jump targets.
        """
        lst = list(self.code[instr_idx])
        lst[field_idx] = value
        self.code[instr_idx] = tuple(lst)

    def current_index(self) -> int:
        """Index that the *next* emitted instruction will occupy."""
        return len(self.code)


# ---------------------------------------------------------------------------
# CompileError
# ---------------------------------------------------------------------------

class CompileError(Exception):
    def __init__(self, msg: str, line: int = 0, col: int = 0):
        location = f" (line {line}, col {col})" if line else ""
        super().__init__(f"{msg}{location}")
        self.line = line
        self.col  = col


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------

# Binary operator → opcode
_BINOP_OPCODES = {
    "+":   "BINARY_ADD",
    "-":   "BINARY_SUB",
    "*":   "BINARY_MUL",
    "/":   "BINARY_DIV",
    "%":   "BINARY_MOD",
    "==":  "BINARY_EQ",
    "!=":  "BINARY_NE",
    "<":   "BINARY_LT",
    "<=":  "BINARY_LE",
    ">":   "BINARY_GT",
    ">=":  "BINARY_GE",
    "and": "BINARY_AND",
    "or":  "BINARY_OR",
}

# Unary operator → opcode
_UNARYOP_OPCODES = {
    "-":   "UNARY_NEG",
    "not": "UNARY_NOT",
}


class Compiler:
    """
    Walks an AST and produces a CodeObject.

    Each Compiler instance handles one chunk (the top-level program
    or one function body).  Function bodies are compiled recursively
    into child CodeObjects stored in the parent's constant pool.
    """

    def __init__(self, name: str = "__main__"):
        self._co = CodeObject(name=name)
        # Stack of (break_patches, continue_patches) for nested loops.
        # Each entry is a list of instruction indices that need patching
        # once the loop's exit / continue target is known.
        self._loop_stack: List[Tuple[List[int], List[int]]] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def compile(self, stmts) -> CodeObject:
        for stmt in stmts:
            self._compile_stmt(stmt)
        return self._co

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def _compile_stmt(self, node: Node) -> None:
        t = type(node)

        if t is Let:
            self._compile_expr(node.expr)
            self._co.emit("STORE_NAME", node.name)

        elif t is Assign:
            self._compile_expr(node.expr)
            self._co.emit("STORE_NAME", node.name)

        elif t is Print:
            # Legacy Print node (kept for safety) — treat as built-in call
            self._compile_expr(node.expr)
            self._co.emit("PRINT")

        elif t is Clear:
            self._co.emit("CLEAR")

        elif t is ExprStmt:
            self._compile_expr(node.expr)
            self._co.emit("POP")   # discard the expression's value

        elif t is If:
            self._compile_if(node)

        elif t is While:
            self._compile_while(node)

        elif t is For:
            self._compile_for(node)

        elif t is Break:
            self._compile_break(node)

        elif t is Continue:
            self._compile_continue(node)

        elif t is Return:
            if node.expr is not None:
                self._compile_expr(node.expr)
            else:
                # bare return → push None
                idx = self._co.add_const(None)
                self._co.emit("LOAD_CONST", idx)
            self._co.emit("RETURN")

        elif t is FnDef:
            self._compile_fn(node)

        else:
            raise CompileError(
                f"Unknown statement node: {type(node).__name__}",
                node.line, node.col,
            )

    # ------------------------------------------------------------------
    # If / elif / else
    # ------------------------------------------------------------------

    def _compile_if(self, node: If) -> None:
        """
        Compile an if/elif/else chain.

        For each branch we emit:
            <condition>
            JUMP_IF_FALSE  → next_branch_or_else
            <body>
            JUMP           → after_if         (backpatched)
        Then the else body (if any).
        All JUMP instructions at the end of bodies jump past the whole chain.
        """
        end_jumps: List[int] = []   # indices of JUMP instrs to patch → after_if

        for cond, body in node.branches:
            # Compile condition
            self._compile_expr(cond)
            # JUMP_IF_FALSE over this branch's body (target patched later)
            jif_idx = self._co.emit("JUMP_IF_FALSE", 0)

            # Compile body
            for stmt in body:
                self._compile_stmt(stmt)

            # Unconditional jump past the whole if/elif/else chain
            jmp_idx = self._co.emit("JUMP", 0)
            end_jumps.append(jmp_idx)

            # Backpatch the JUMP_IF_FALSE → instruction right after the JUMP
            self._co.patch(jif_idx, 1, self._co.current_index())

        # Compile optional else body
        for stmt in node.else_body:
            self._compile_stmt(stmt)

        # Backpatch all end-of-branch JUMPs → here (after everything)
        after = self._co.current_index()
        for idx in end_jumps:
            self._co.patch(idx, 1, after)

    # ------------------------------------------------------------------
    # While loop
    # ------------------------------------------------------------------

    def _compile_while(self, node: While) -> None:
        """
        loop_start:
            <condition>
            JUMP_IF_FALSE  → after_loop
            <body>
            JUMP           → loop_start
        after_loop:
        """
        loop_start = self._co.current_index()

        self._compile_expr(node.condition)
        jif_idx = self._co.emit("JUMP_IF_FALSE", 0)   # patch later

        # Push loop frame so break/continue know where to patch
        break_patches:    List[int] = []
        continue_patches: List[int] = []
        self._loop_stack.append((break_patches, continue_patches))

        for stmt in node.body:
            self._compile_stmt(stmt)

        self._loop_stack.pop()

        # Patch continue → top of loop (before condition)
        for idx in continue_patches:
            self._co.patch(idx, 1, loop_start)

        # Back-edge: unconditional jump to loop_start
        self._co.emit("JUMP", loop_start)

        # After loop — patch JUMP_IF_FALSE and break statements here
        after_loop = self._co.current_index()
        self._co.patch(jif_idx, 1, after_loop)
        for idx in break_patches:
            self._co.patch(idx, 1, after_loop)

    # ------------------------------------------------------------------
    # For loop
    # ------------------------------------------------------------------

    def _compile_for(self, node: For) -> None:
        """
        Desugars  for i = start to end { body }  into:

            i = start
        loop_start:
            <i < end>
            JUMP_IF_FALSE  → after_loop
            <body>
        continue_target:
            i = i + 1
            JUMP           → loop_start
        after_loop:
        """
        # Initialise loop variable
        self._compile_expr(node.start)
        self._co.emit("STORE_NAME", node.var_name)

        loop_start = self._co.current_index()

        # Condition:  i < end
        self._co.emit("LOAD_NAME", node.var_name)
        self._compile_expr(node.end)
        self._co.emit("BINARY_LT")
        jif_idx = self._co.emit("JUMP_IF_FALSE", 0)   # patch later

        # Push loop frame
        break_patches:    List[int] = []
        continue_patches: List[int] = []
        self._loop_stack.append((break_patches, continue_patches))

        for stmt in node.body:
            self._compile_stmt(stmt)

        self._loop_stack.pop()

        # continue_target: increment i
        continue_target = self._co.current_index()
        self._co.emit("LOAD_NAME", node.var_name)
        one_idx = self._co.add_const(1)
        self._co.emit("LOAD_CONST", one_idx)
        self._co.emit("BINARY_ADD")
        self._co.emit("STORE_NAME", node.var_name)

        # Patch continue → increment step
        for idx in continue_patches:
            self._co.patch(idx, 1, continue_target)

        # Back-edge
        self._co.emit("JUMP", loop_start)

        # After loop
        after_loop = self._co.current_index()
        self._co.patch(jif_idx, 1, after_loop)
        for idx in break_patches:
            self._co.patch(idx, 1, after_loop)

    # ------------------------------------------------------------------
    # Break / Continue
    # ------------------------------------------------------------------

    def _compile_break(self, node: Break) -> None:
        if not self._loop_stack:
            raise CompileError("'break' outside loop", node.line, node.col)
        break_patches, _ = self._loop_stack[-1]
        idx = self._co.emit("JUMP", 0)   # target patched when loop ends
        break_patches.append(idx)

    def _compile_continue(self, node: Continue) -> None:
        if not self._loop_stack:
            raise CompileError("'continue' outside loop", node.line, node.col)
        _, continue_patches = self._loop_stack[-1]
        idx = self._co.emit("JUMP", 0)   # target patched when loop ends
        continue_patches.append(idx)

    # ------------------------------------------------------------------
    # Function definition
    # ------------------------------------------------------------------

    def _compile_fn(self, node: FnDef) -> None:
        """
        Compile the function body into a child CodeObject, store it in
        the parent's constant pool, then emit MAKE_FUNCTION.
        """
        child = Compiler(name=node.name)
        body_co = child.compile(node.body)

        co_idx = self._co.add_const(body_co)
        self._co.emit("MAKE_FUNCTION", node.name, node.params, co_idx)

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------

    def _compile_expr(self, node: Node) -> None:
        t = type(node)

        if t is NumberLit:
            idx = self._co.add_const(node.value)
            self._co.emit("LOAD_CONST", idx)

        elif t is StringLit:
            idx = self._co.add_const(node.value)
            self._co.emit("LOAD_CONST", idx)

        elif t is BoolLit:
            idx = self._co.add_const(node.value)
            self._co.emit("LOAD_CONST", idx)

        elif t is Var:
            self._co.emit("LOAD_NAME", node.name)

        elif t is BinOp:
            opcode = _BINOP_OPCODES.get(node.op)
            if opcode is None:
                raise CompileError(
                    f"Unknown binary operator '{node.op}'",
                    node.line, node.col,
                )
            self._compile_expr(node.left)
            self._compile_expr(node.right)
            self._co.emit(opcode)

        elif t is UnaryOp:
            opcode = _UNARYOP_OPCODES.get(node.op)
            if opcode is None:
                raise CompileError(
                    f"Unknown unary operator '{node.op}'",
                    node.line, node.col,
                )
            self._compile_expr(node.expr)
            self._co.emit(opcode)

        elif t is ListLit:
            for elem in node.elements:
                self._compile_expr(elem)
            self._co.emit("BUILD_LIST", len(node.elements))

        elif t is DictLit:
            for key, val in node.entries:
                self._compile_expr(key)
                self._compile_expr(val)
            self._co.emit("BUILD_DICT", len(node.entries))

        elif t is Index:
            self._compile_expr(node.collection)
            self._compile_expr(node.index)
            self._co.emit("BINARY_SUBSCR")

        elif t is Call:
            for arg in node.args:
                self._compile_expr(arg)
            self._co.emit("CALL_FUNCTION", node.name, len(node.args))

        else:
            raise CompileError(
                f"Unknown expression node: {type(node).__name__}",
                node.line, node.col,
            )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def compile_ast(stmts) -> CodeObject:
    """
    Compile a sequence of top-level AST nodes into a CodeObject
    ready for the VM to execute.
    """
    return Compiler(name="__main__").compile(stmts)