try:
    import readline  # Linux/macOS
except ImportError:
    import pyreadline3 as readline  # Windows alternative

from axon.parser import Parser, ParseError
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

            # ---- parse statements safely ----
            try:
                parser = Parser(code)
                statements = parser.parse()
            except ParseError as e:
                print(f"[!!] Syntax error: {e}")
                continue

            # ---- compile program safely ----
            try:
                co = compile_program(statements)
            except Exception as e:
                print(f"[!!] Compile error: {e}")
                continue

            # ---- run in VM safely ----
            try:
                vm.push_frame(co)
                vm.run()
            except Exception as e:
                print(f"[!!] Runtime error: {e}")

        except EOFError:
            print("\nExiting Axon REPL.")
            break
        except KeyboardInterrupt:
            print("\n[!!] Keyboard interrupt — REPL still alive.")
            continue
        except Exception as e:
            print(f"[!!] Unexpected error: {e}")
            continue

if __name__ == "__main__":
    repl()
