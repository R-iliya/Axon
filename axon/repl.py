try:
    import readline  # for Linux/macOS
except ImportError:
    import pyreadline3 as readline  # Windows alternative

from axon.parser import Parser
from axon.compiler import compile_program  # optional for later VM
from axon.vm import VM                       # optional for later VM
from axon import sema                        # optional for later VM

PROMPT = ">> "

def repl():
    print("Axon REPL — enter statements ending with ';'. Ctrl-D to exit.")
    vm = VM()  # optional, only if you plan to use your VM
    context = {}  # stores variables and runtime context

    while True:
        try:
            code = input(PROMPT)
            if not code.strip():
                continue

            # ---- parse statements ----
            parser = Parser(code)
            statements = parser.parse()  # returns list of statement nodes

            # ---- execute statements ----
            for stmt in statements:
                stmt.eval(context)

        except EOFError:
            print("\nExiting Axon REPL.")
            break
        except Exception as e:
            print(f"[!!] Parse/runtime error: {e}")
            continue

if __name__ == "__main__":
    repl()
