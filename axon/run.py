# axon/run.py
from axon.lexer import tokenize
from axon.parser import parse_text
from axon import sema
from axon.compiler import compile_program
from axon.vm import VM
import sys

def run_file(path: str):
    # Use 'with' so the file is safely closed after reading
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    
    prog = parse_text(src)
    sema.analyze(prog)
    co = compile_program(prog)
    vm = VM()
    vm.push_frame(co)
    vm.run()
    
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m axon.run <file.ax>")
        raise SystemExit(1)
    run_file(sys.argv[1])
