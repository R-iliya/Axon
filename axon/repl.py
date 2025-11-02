# axon/repl.py
try:
    import readline  # for Linux/macOS
except ImportError:
    import pyreadline3 as readline  # Windows alternative (install below)

from axon.parser import Parser
from axon.compiler import compile_program
from axon.vm import VM
from axon import sema
import sys

PROMPT = "axon> "

context = {}
stmt.eval(context)

def repl():
    vm = VM()
    buffer = ""
    print("Axon REPL — enter statements ending with ';'. Ctrl-D to exit.")
    try:
        while True:
            try:
                code = input("axon> ")
                parser = Parser(code)
                statements = parser.parse()
                for stmt in statements:
                    stmt.eval(context)
            except EOFError:
                break
            except Exception as e:
                print(f"[!!] Parse error: {e}")
                buffer = ""
                continue
            try:
                sema.analyze(prog)
                co = compile_program(prog)
                vm.push_frame(co)
                vm.run()
            except Exception as e:
                print("[!!] Runtime error:", e)
            buffer = ""
    except KeyboardInterrupt:
        print("\nInterrupted.")
    print("Bye.")

if __name__ == "__main__":
    repl()
