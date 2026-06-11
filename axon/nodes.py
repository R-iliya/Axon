# axon/nodes.py
"""
AST node definitions for the Axon language.

All nodes are immutable dataclasses — pure data, zero behaviour.
Execution is handled by a separate tree-walk interpreter or bytecode compiler
that walks this tree.

Node hierarchy
--------------
Expr (produce a value)
  NumberLit      – 42 | 3.14
  StringLit      – "hello"
  BoolLit        – true | false
  Var            – x
  BinOp          – a + b,  x == y,  p and q  …
  UnaryOp        – -x | not y
  ListLit        – [1, 2, 3]
  DictLit        – {"a": 1, "b": 2}
  Index          – collection[idx]
  Call           – foo(1, "bar")

Stmt (perform an action, produce no value)
  Let            – let x = expr;          (declaration OR re-assignment)
  Assign         – x = expr;              (bare re-assignment, no 'let')
  Print          – print(expr);
  Clear          – cls;
  If             – if … { } elif … { } else { }
  While          – while cond { }
  For            – for i = start to end { }
  Break          – break;
  Continue       – continue;
  Return         – return expr;
  FnDef          – fn name(params) { body }
  ExprStmt       – a standalone expression used as a statement
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Node:
    """Base class for every AST node."""
    line: int
    col:  int


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NumberLit(Node):
    """Integer or float literal.  e.g. 42  |  3.14"""
    value: int | float


@dataclass(frozen=True)
class StringLit(Node):
    """String literal (already cooked by the lexer).  e.g. "hello\\nworld" """
    value: str


@dataclass(frozen=True)
class BoolLit(Node):
    """Boolean literal.  true | false"""
    value: bool


@dataclass(frozen=True)
class Var(Node):
    """Variable reference.  e.g. x"""
    name: str


@dataclass(frozen=True)
class BinOp(Node):
    """
    Binary operation.

    op is one of:
      arithmetic : + - * / %
      comparison : == != < > <= >=
      logical    : and or
    """
    left:  Node
    op:    str
    right: Node


@dataclass(frozen=True)
class UnaryOp(Node):
    """
    Unary operation.

    op is one of: -  not
    """
    op:   str
    expr: Node


@dataclass(frozen=True)
class ListLit(Node):
    """List literal.  e.g. [1, 2, 3]"""
    elements: Tuple[Node, ...]


@dataclass(frozen=True)
class DictLit(Node):
    """
    Dict literal.  e.g. {"key": value, ...}
    entries is a tuple of (key_node, value_node) pairs.
    """
    entries: Tuple[Tuple[Node, Node], ...]


@dataclass(frozen=True)
class Index(Node):
    """
    Subscript / index access.  e.g. arr[0]  |  d["key"]
    Supports chained indexing: arr[0][1] becomes Index(Index(arr, 0), 1).
    """
    collection: Node
    index:      Node


@dataclass(frozen=True)
class Call(Node):
    """
    Function call.  e.g. foo(1, "bar")
    args is a tuple of expression nodes.
    """
    name: str
    args: Tuple[Node, ...]


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Let(Node):
    """
    Variable declaration (and initialisation).  e.g. let x = 5;
    Creates the variable in the current scope if it doesn't exist.
    """
    name: str
    expr: Node


@dataclass(frozen=True)
class Assign(Node):
    """
    Bare re-assignment (no 'let').  e.g. x = 10;
    The variable must already exist in an enclosing scope.
    """
    name: str
    expr: Node


@dataclass(frozen=True)
class Print(Node):
    """Built-in print statement.  e.g. print(expr);"""
    expr: Node


@dataclass(frozen=True)
class Clear(Node):
    """Clear the terminal screen.  cls;"""


@dataclass(frozen=True)
class If(Node):
    """
    if / elif / else chain.

    branches  : one or more (condition, body) pairs.
                The first pair is the 'if' branch;
                subsequent pairs are 'elif' branches.
    else_body : optional list of statements for the final 'else' block.

    e.g.
        if x > 0 {
            print("pos");
        } elif x == 0 {
            print("zero");
        } else {
            print("neg");
        }
    """
    branches:  Tuple[Tuple[Node, Tuple[Node, ...]], ...]
    else_body: Tuple[Node, ...]


@dataclass(frozen=True)
class While(Node):
    """
    While loop.  e.g. while cond { body }
    """
    condition: Node
    body:      Tuple[Node, ...]


@dataclass(frozen=True)
class For(Node):
    """
    Counted for loop.  e.g. for i = 0 to 10 { body }

    var_name : loop variable name (created / overwritten each iteration)
    start    : start expression (inclusive)
    end      : end expression   (exclusive, like Python range)
    body     : tuple of statements
    """
    var_name: str
    start:    Node
    end:      Node
    body:     Tuple[Node, ...]


@dataclass(frozen=True)
class Break(Node):
    """break;  — exit the nearest enclosing loop."""


@dataclass(frozen=True)
class Continue(Node):
    """continue;  — skip to the next iteration of the nearest enclosing loop."""


@dataclass(frozen=True)
class Return(Node):
    """
    return expr;  — return a value from a function.
    expr is None for a bare 'return;' (returns null / None).
    """
    expr: Optional[Node]


@dataclass(frozen=True)
class FnDef(Node):
    """
    Function definition.  e.g. fn greet(name) { print("hi " + name); }

    name   : function name
    params : tuple of parameter name strings
    body   : tuple of statements
    """
    name:   str
    params: Tuple[str, ...]
    body:   Tuple[Node, ...]


@dataclass(frozen=True)
class ExprStmt(Node):
    """
    A bare expression used as a statement (result is discarded).
    e.g.  greet("Axon");   — a call whose return value isn't captured.
    """
    expr: Node