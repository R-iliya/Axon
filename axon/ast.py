# axon/ast.py
from dataclasses import dataclass
from typing import List, Any, Optional

@dataclass(frozen=True)
class Node:
    pass

@dataclass(frozen=True)
class Program(Node):
    statements: List[Node]

@dataclass(frozen=True)
class Number(Node):
    value: Any   # int or float
    lineno: int
    col: int

@dataclass(frozen=True)
class Var(Node):
    name: str
    lineno: int
    col: int

@dataclass(frozen=True)
class BinOp(Node):
    left: Node
    op: str
    right: Node
    lineno: int
    col: int

@dataclass(frozen=True)
class Assign(Node):
    name: str
    value: Node
    lineno: int
    col: int

@dataclass(frozen=True)
class Print(Node):
    expr: Node
    lineno: int
    col: int
