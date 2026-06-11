# axon/sema.py
"""
Semantic analyser for the Axon language.

Performs four analysis passes over the AST before compilation:

  1. Scope / undefined-variable detection
     - Tracks every name that is assigned (Let, Assign, FnDef, params)
     - Warns when a name is used (Var, Call) before any assignment in scope
     - Handles nested function scopes correctly

  2. Type-mismatch hints
     - Catches statically obvious mismatches on literal operands
       e.g.  -"hello"   not 42   "a" - "b"
     - Only fires when BOTH sides are literals (we have no full type system)

  3. Return-path checking
     - Warns if a function body might not return a value on all paths
     - Understands if/else chains: both branches must return
     - break / continue do not count as returns

  4. Dead-code detection
     - Warns about any statement that appears after a Return, Break,
       or Continue inside the same block — it can never execute

All issues are collected into SemanticWarning objects.
analyse() returns a list of warnings; it never raises.
Callers decide whether to print, promote to errors, or ignore them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

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
# SemanticWarning
# ---------------------------------------------------------------------------

@dataclass
class SemanticWarning:
    kind:    str    # e.g. "undefined_name", "type_mismatch", …
    message: str
    line:    int
    col:     int

    def __str__(self) -> str:
        return f"[{self.kind}] line {self.line}, col {self.col}: {self.message}"


# ---------------------------------------------------------------------------
# Scope  — lightweight symbol table for one lexical scope
# ---------------------------------------------------------------------------

class Scope:
    """
    A simple set-based scope that tracks which names have been defined.
    Scopes chain upward via *parent*.
    """

    def __init__(self, parent: Optional[Scope] = None):
        self._names: Set[str] = set()
        self.parent = parent

    def define(self, name: str) -> None:
        self._names.add(name)

    def is_defined(self, name: str) -> bool:
        if name in self._names:
            return True
        if self.parent is not None:
            return self.parent.is_defined(name)
        return False

    def child(self) -> "Scope":
        return Scope(parent=self)


# ---------------------------------------------------------------------------
# Helpers — static type inference on literal nodes
# ---------------------------------------------------------------------------

# Maps node type → Axon type name (for literal nodes only)
_LITERAL_TYPES = {
    NumberLit: "number",
    StringLit: "string",
    BoolLit:   "bool",
}

def _literal_type(node: Node) -> Optional[str]:
    """Return the type name if *node* is a literal, else None."""
    return _LITERAL_TYPES.get(type(node))


# Which binary operators are valid for which literal type combinations.
# Keys are (left_type, right_type); value is a set of allowed operators.
_VALID_BINOPS: dict = {
    ("number", "number"): {"+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">="},
    ("string", "string"): {"+", "==", "!="},
    ("bool",   "bool"):   {"and", "or", "==", "!="},
    ("number", "bool"):   {"==", "!="},
    ("bool",   "number"): {"==", "!="},
    ("string", "number"): {"==", "!="},
    ("number", "string"): {"==", "!="},
    ("string", "bool"):   {"==", "!="},
    ("bool",   "string"): {"==", "!="},
}

# Which unary operators are valid for which literal types.
_VALID_UNARYOPS: dict = {
    "-":   {"number"},
    "not": {"bool", "number"},   # 'not' on numbers is valid (truthy check)
}


# ---------------------------------------------------------------------------
# Analyser
# ---------------------------------------------------------------------------

class Analyser:
    def __init__(self):
        self._warnings: List[SemanticWarning] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _warn(self, kind: str, message: str, node: Node) -> None:
        self._warnings.append(
            SemanticWarning(kind=kind, message=message, line=node.line, col=node.col)
        )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def analyse(self, stmts) -> List[SemanticWarning]:
        # Seed the global scope with all built-in names so we don't
        # falsely warn about calls to print, len, type, etc.
        global_scope = Scope()
        for name in _BUILTIN_NAMES:
            global_scope.define(name)

        self._check_block(stmts, global_scope, inside_fn=False)
        return self._warnings

    # ------------------------------------------------------------------
    # Pass driver — walk a block of statements
    # ------------------------------------------------------------------

    def _check_block(
        self,
        stmts,
        scope: Scope,
        inside_fn: bool,
    ) -> bool:
        """
        Walk *stmts*, running all four checks.
        Returns True if the block is guaranteed to return (for pass 3).
        """
        guaranteed_return = False

        for i, stmt in enumerate(stmts):

            # Pass 4 — dead code after terminator
            if guaranteed_return:
                self._warn(
                    "dead_code",
                    f"Unreachable statement after return/break/continue",
                    stmt,
                )
                # No point analysing dead stmts — but we'll still walk
                # them so we catch other errors inside them

            # Dispatch all passes on this statement
            stmt_returns = self._check_stmt(stmt, scope, inside_fn)

            if stmt_returns:
                guaranteed_return = True

        return guaranteed_return

    # ------------------------------------------------------------------
    # Pass 1-4 on a single statement
    # Returns True if this statement unconditionally terminates the block
    # ------------------------------------------------------------------

    def _check_stmt(self, node: Node, scope: Scope, inside_fn: bool) -> bool:
        t = type(node)

        # -- Let / Assign ----------------------------------------------

        if t is Let:
            self._check_expr(node.expr, scope)
            scope.define(node.name)
            return False

        elif t is Assign:
            self._check_expr(node.expr, scope)
            if not scope.is_defined(node.name):
                self._warn(
                    "undefined_name",
                    f"Assignment to '{node.name}' before declaration — "
                    f"use 'let {node.name} = …' to declare it first",
                    node,
                )
            # Define it anyway so we don't cascade warnings
            scope.define(node.name)
            return False

        # -- Print (legacy node) ---------------------------------------

        elif t is Print:
            self._check_expr(node.expr, scope)
            return False

        # -- Clear -----------------------------------------------------

        elif t is Clear:
            return False

        # -- ExprStmt --------------------------------------------------

        elif t is ExprStmt:
            self._check_expr(node.expr, scope)
            return False

        # -- If / elif / else ------------------------------------------

        elif t is If:
            return self._check_if(node, scope, inside_fn)

        # -- While -----------------------------------------------------

        elif t is While:
            self._check_expr(node.condition, scope)
            loop_scope = scope.child()
            self._check_block(node.body, loop_scope, inside_fn)
            # A while loop does not guarantee a return (might not execute)
            return False

        # -- For -------------------------------------------------------

        elif t is For:
            self._check_expr(node.start, scope)
            self._check_expr(node.end, scope)
            loop_scope = scope.child()
            loop_scope.define(node.var_name)
            self._check_block(node.body, loop_scope, inside_fn)
            return False

        # -- Break / Continue ------------------------------------------

        elif t is Break or t is Continue:
            # These terminate the current iteration / loop but not a fn
            return True   # treat as "terminates this block path"

        # -- Return ----------------------------------------------------

        elif t is Return:
            if not inside_fn:
                self._warn(
                    "invalid_return",
                    "'return' used outside of a function",
                    node,
                )
            if node.expr is not None:
                self._check_expr(node.expr, scope)
            return True   # definitely terminates

        # -- FnDef -----------------------------------------------------

        elif t is FnDef:
            return self._check_fn(node, scope)

        else:
            return False

    # ------------------------------------------------------------------
    # If / elif / else  — pass 3 logic
    # ------------------------------------------------------------------

    def _check_if(self, node: If, scope: Scope, inside_fn: bool) -> bool:
        """
        Returns True only if every branch is guaranteed to return.
        That requires:
          - every 'if'/'elif' branch returns, AND
          - there is an 'else' branch that also returns.
        """
        all_return = True

        for cond, body in node.branches:
            self._check_expr(cond, scope)
            branch_scope = scope.child()
            branch_returns = self._check_block(body, branch_scope, inside_fn)
            if not branch_returns:
                all_return = False

        if node.else_body:
            else_scope = scope.child()
            else_returns = self._check_block(node.else_body, else_scope, inside_fn)
            if not else_returns:
                all_return = False
        else:
            # No else branch → cannot guarantee a return
            all_return = False

        return all_return

    # ------------------------------------------------------------------
    # Function definition
    # ------------------------------------------------------------------

    def _check_fn(self, node: FnDef, parent_scope: Scope) -> bool:
        fn_scope = parent_scope.child()
        for param in node.params:
            fn_scope.define(param)

        guaranteed = self._check_block(node.body, fn_scope, inside_fn=True)

        # Pass 3 — warn if function might not return
        if not guaranteed:
            self._warn(
                "missing_return",
                f"Function '{node.name}' may not return a value on all paths",
                node,
            )

        # The FnDef itself defines the function name in the parent scope
        parent_scope.define(node.name)
        return False   # defining a function doesn't terminate the outer block

    # ------------------------------------------------------------------
    # Expression checker  (passes 1 & 2)
    # ------------------------------------------------------------------

    def _check_expr(self, node: Node, scope: Scope) -> None:
        t = type(node)

        if t is NumberLit or t is StringLit or t is BoolLit:
            pass   # literals are always fine

        elif t is Var:
            if not scope.is_defined(node.name):
                self._warn(
                    "undefined_name",
                    f"'{node.name}' is used but never defined",
                    node,
                )

        elif t is BinOp:
            self._check_expr(node.left, scope)
            self._check_expr(node.right, scope)
            self._check_binop_types(node)

        elif t is UnaryOp:
            self._check_expr(node.expr, scope)
            self._check_unaryop_types(node)

        elif t is ListLit:
            for elem in node.elements:
                self._check_expr(elem, scope)

        elif t is DictLit:
            for key, val in node.entries:
                self._check_expr(key, scope)
                self._check_expr(val, scope)

        elif t is Index:
            self._check_expr(node.collection, scope)
            self._check_expr(node.index, scope)

        elif t is Call:
            if not scope.is_defined(node.name):
                self._warn(
                    "undefined_name",
                    f"'{node.name}' is called but never defined",
                    node,
                )
            for arg in node.args:
                self._check_expr(arg, scope)

    # ------------------------------------------------------------------
    # Pass 2 helpers — type mismatch on literals
    # ------------------------------------------------------------------

    def _check_binop_types(self, node: BinOp) -> None:
        lt = _literal_type(node.left)
        rt = _literal_type(node.right)
        if lt is None or rt is None:
            return   # can't infer statically — skip

        allowed = _VALID_BINOPS.get((lt, rt), set())
        if node.op not in allowed:
            self._warn(
                "type_mismatch",
                f"Operator '{node.op}' cannot be applied to "
                f"'{lt}' and '{rt}'",
                node,
            )

    def _check_unaryop_types(self, node: UnaryOp) -> None:
        et = _literal_type(node.expr)
        if et is None:
            return

        allowed = _VALID_UNARYOPS.get(node.op, set())
        if et not in allowed:
            self._warn(
                "type_mismatch",
                f"Unary operator '{node.op}' cannot be applied to '{et}'",
                node,
            )


# ---------------------------------------------------------------------------
# Built-in names — seeded into the global scope so they don't trigger
# "undefined_name" warnings.
# ---------------------------------------------------------------------------

_BUILTIN_NAMES: Set[str] = {
    "print", "len", "type", "int", "float", "str", "bool",
    "range", "append", "pop", "keys", "values",
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def analyse(stmts) -> List[SemanticWarning]:
    """
    Run all semantic checks on *stmts* (a list/tuple of AST nodes).
    Returns a (possibly empty) list of SemanticWarning objects.
    Never raises.
    """
    return Analyser().analyse(stmts)