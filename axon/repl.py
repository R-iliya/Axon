# axon/repl.py
try:
    import readline  # for Linux/macOS
except ImportError:
    import pyreadline3 as readline  # Windows alternative (install below)

from axon.parser import parse_text
from axon.compiler import compile_program
from axon.vm import VM
from axon import sema
import sys

PROMPT = "axon> "

def repl():
    vm = VM()
    buffer = ""
    print("Axon REPL — enter statements ending with ';'. Ctrl-D to exit.")
    try:
        while True:
            try:
                line = input(PROMPT)
            except EOFError:
                print()
                break
            buffer += line + "\n"
            if ";" not in line:
                continue
            try:
                prog = parse_text(buffer)
            except Exception as e:
                print("Parse error:", e)
                buffer = ""
                continue
            try:
                sema.analyze(prog)
                co = compile_program(prog)
                vm.push_frame(co)
                vm.run()
            except Exception as e:
                print("Runtime error:", e)
            buffer = ""
    except KeyboardInterrupt:
        print("\nInterrupted.")
    print("Bye.")

if __name__ == "__main__":
    repl()
