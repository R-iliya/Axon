# tests/test_basic.py
import io
import sys
from axon.run import run_file
import os
import pytest

def capture_run(path):
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        run_file(path)
        return sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

def test_hello_example(tmp_path):
    p = tmp_path / "ex.ax"
    p.write_text("""
let x = 5;
let y = 10;
print(y);
print(x + 6);
""")
    out = capture_run(str(p))
    # expected: y = 10 and 11 from the second print
    assert "10" in out
    assert "11" in out
