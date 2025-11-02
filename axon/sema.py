# axon/sema.py
from axon.ast import *
from typing import Set

class SemanticError(Exception):
    pass

def analyze(program: Program):
    """
    Minimal semantic analysis:
     - ensure assignments have a name (done by parser)
     - (optional) warn about uses of undefined names at compile-time is tricky for dynamic languages.
    For now: collect assigned names and return a simple symbol table.
    """
    assigned: Set[str] = set()
    used: Set[str] = set()

    for stmt in program.statements:
        if isinstance(stmt, Assign):
            assigned.add(stmt.name)
            # inspect rhs for used names
            collect_names(stmt.value, used)
        elif isinstance(stmt, Print):
            collect_names(stmt.expr, used)

    # note: do not raise on uses of names that are not yet assigned (dynamic)
    # but we can return symbol info for tooling.
    return {"assigned": assigned, "used": used}


def collect_names(node, used: Set[str]):
    # recursively collect Var names used
    if isinstance(node, Var):
        used.add(node.name)
    elif isinstance(node, BinOp):
        collect_names(node.left, used)
        collect_names(node.right, used)
    elif isinstance(node, Number):
        pass
    else:
        # extend later for other node types
        pass
