# axon/run.py
"""
File runner for the Axon language.

Usage:
    python -m axon.run <file.ax>

Pipeline:
    source → lexer → parser → sema → compiler → vm
"""

from __future__ import annotations

import sys
from pathlib import Path

from axon.lexer import LexError
from axon.parser import parse, ParseError
from axon.sema import analyse
from axon.compiler import compile_ast, CompileError
from axon.vm import VM, AxonRuntimeError


def run_source(source: str, filepath: str = "<string>") -> None:
    """
    Run raw Axon source through the full pipeline.
    Prints friendly error messages and exits on failure.
    """

    # ── 1. Parse ──────────────────────────────────────────────────────
    try:
        stmts = parse(source)
    except LexError as e:
        print(f"[LexError] {filepath}: {e}", file=sys.stderr)
        sys.exit(1)
    except ParseError as e:
        print(f"[ParseError] {filepath}: {e}", file=sys.stderr)
        sys.exit(1)

    # ── 2. Semantic analysis ──────────────────────────────────────────
    warnings = analyse(stmts)
    for w in warnings:
        print(f"[Warning] {filepath}: {w}", file=sys.stderr)

    # ── 3. Compile ────────────────────────────────────────────────────
    try:
        co = compile_ast(stmts)
    except CompileError as e:
        print(f"[CompileError] {filepath}: {e}", file=sys.stderr)
        sys.exit(1)

    # ── 4. Execute ────────────────────────────────────────────────────
    try:
        VM().execute(co)
    except AxonRuntimeError as e:
        print(f"[RuntimeError] {filepath}: {e}", file=sys.stderr)
        sys.exit(1)


def run_file(filepath: str) -> None:
    """Read *filepath* and run it through the pipeline."""
    path = Path(filepath)

    if not path.exists():
        print(f"[Error] File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    if path.suffix != ".ax":
        print(f"[Warning] Expected a .ax file, got '{path.suffix}'", file=sys.stderr)

    source = path.read_text(encoding="utf-8")
    run_source(source, filepath=filepath)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m axon.run <file.ax>", file=sys.stderr)
        sys.exit(1)

    run_file(sys.argv[1])