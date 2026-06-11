# axon/repl.py
"""
Interactive REPL for the Axon language.

Usage:
    python -m axon.repl

Features:
  - Persistent VM across inputs (variables survive between lines)
  - Semantic warnings shown inline
  - Multi-line input — keep typing until braces are balanced
  - Special commands:  :help  :clear  :reset  :exit
  - Ctrl-D or Ctrl-C to exit gracefully
"""

from __future__ import annotations

import sys

from axon.lexer import LexError
from axon.parser import parse, ParseError
from axon.sema import analyse
from axon.compiler import compile_ast, CompileError
from axon.vm import VM, AxonRuntimeError


# ---------------------------------------------------------------------------
# Colours (disabled automatically if not a TTY)
# ---------------------------------------------------------------------------

_USE_COLOR = sys.stdout.isatty()

def _c(code: str, text: str) -> str:
    if not _USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"

def _red(t: str)    -> str: return _c("31", t)
def _yellow(t: str) -> str: return _c("33", t)
def _cyan(t: str)   -> str: return _c("36", t)
def _bold(t: str)   -> str: return _c("1",  t)
def _dim(t: str)    -> str: return _c("2",  t)


# ---------------------------------------------------------------------------
# Brace balance — used to detect incomplete multi-line input
# ---------------------------------------------------------------------------

def _brace_balance(source: str) -> int:
    """
    Return the net open-brace count in *source* (ignoring braces inside
    string literals and comments).  Positive → still open; 0 → balanced.
    """
    balance = 0
    in_str  = False
    i = 0
    while i < len(source):
        ch = source[i]
        if ch == '"' and not in_str:
            in_str = True
        elif ch == '"' and in_str:
            in_str = False
        elif ch == '\\' and in_str:
            i += 1                      # skip escaped char
        elif not in_str:
            if ch == '{':
                balance += 1
            elif ch == '}':
                balance -= 1
            elif ch == '/' and i + 1 < len(source) and source[i + 1] == '/':
                # line comment — skip to end of line
                while i < len(source) and source[i] != '\n':
                    i += 1
        i += 1
    return balance


# ---------------------------------------------------------------------------
# Special REPL commands
# ---------------------------------------------------------------------------

_HELP_TEXT = f"""
{_bold('Axon REPL — special commands')}

  {_cyan(':help')}     show this message
  {_cyan(':clear')}    clear the screen
  {_cyan(':reset')}    reset the VM (wipe all variables and functions)
  {_cyan(':exit')}     quit the REPL

{_bold('Language quick-reference')}

  {_dim('Variables')}     let x = 10;
  {_dim('Reassign')}      x = 20;
  {_dim('Print')}         print(x);
  {_dim('If/elif/else')}  if x > 0 {{ print("pos"); }} else {{ print("neg"); }}
  {_dim('While')}         while x < 10 {{ x = x + 1; }}
  {_dim('For')}           for i = 0 to 5 {{ print(i); }}
  {_dim('Function')}      fn add(a, b) {{ return a + b; }}
  {_dim('Call')}          let r = add(3, 4);
  {_dim('List')}          let arr = [1, 2, 3];
  {_dim('Dict')}          let d = {{"key": "value"}};
  {_dim('Index')}         print(arr[0]);
  {_dim('Types')}         number  string  bool  list  dict
  {_dim('Built-ins')}     print  len  type  int  float  str  bool
                   append  pop  keys  values  range
"""


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------

PROMPT_MAIN = _bold(_cyan("axon> "))
PROMPT_CONT = _bold(_cyan("  ... "))


class Repl:
    def __init__(self):
        self._vm = VM()

    def _reset(self) -> None:
        self._vm = VM()
        print(_dim("VM reset — all variables cleared."))

    def _run_source(self, source: str) -> None:
        """Run one chunk of source through the full pipeline."""

        # Parse
        try:
            stmts = parse(source)
        except LexError as e:
            print(_red(f"[LexError] {e}"))
            return
        except ParseError as e:
            print(_red(f"[ParseError] {e}"))
            return

        if not stmts:
            return

        # Sema warnings
        warnings = analyse(stmts)
        for w in warnings:
            print(_yellow(f"[Warning] {w}"))

        # Compile
        try:
            co = compile_ast(stmts)
        except CompileError as e:
            print(_red(f"[CompileError] {e}"))
            return

        # Execute on the persistent VM
        try:
            self._vm.execute(co)
        except AxonRuntimeError as e:
            print(_red(f"[RuntimeError] {e}"))

    def _read_input(self) -> str | None:
        """
        Read one logical chunk of input, handling multi-line blocks.
        Returns None on EOF.
        """
        lines = []
        prompt = PROMPT_MAIN

        while True:
            try:
                line = input(prompt)
            except EOFError:
                return None

            lines.append(line)
            source = "\n".join(lines)

            # If braces are still open, keep reading continuation lines
            if _brace_balance(source) > 0:
                prompt = PROMPT_CONT
                continue

            return source

    def run(self) -> None:
        print(
            _bold("Axon REPL")
            + _dim(" — type :help for commands, Ctrl-D to exit")
        )
        print()

        while True:
            try:
                source = self._read_input()
            except KeyboardInterrupt:
                print()
                continue

            # EOF (Ctrl-D)
            if source is None:
                print(_dim("\nGoodbye."))
                break

            stripped = source.strip()
            if not stripped:
                continue

            # Special commands
            if stripped == ":help":
                print(_HELP_TEXT)
            elif stripped == ":clear":
                import os
                os.system("cls" if os.name == "nt" else "clear")
            elif stripped == ":reset":
                self._reset()
            elif stripped in (":exit", ":quit"):
                print(_dim("Goodbye."))
                break
            else:
                self._run_source(stripped)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def repl() -> None:
    Repl().run()


if __name__ == "__main__":
    repl()