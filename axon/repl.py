try:
    import readline  # Linux/macOS
except ImportError:
    import pyreadline3 as readline  # Windows

from axon.parser import Parser
from axon.compiler import compile_program
from axon.vm import VM

PROMPT = ">> "

def repl():
    print("Axon REPL — enter statements ending with ';'. Ctrl-D to exit.")
    vm = VM()  # single persistent VM for REPL

    while True:
        try:
            code = input(PROMPT)
            if not code.strip():
                continue

            # ---- parse statements ----
            parser = Parser(code)
            statements = parser.parse()  # returns list of statement nodes

            # ---- compile and run in VM ----
            co = compile_program(statements)
            vm.push_frame(co)
            vm.run()

        except EOFError:
            print("\nExiting Axon REPL.")
            break
        except Exception as e:
            print(f"[!!] Parse/runtime error: {e}")
            continue

if __name__ == "__main__":
    repl()
