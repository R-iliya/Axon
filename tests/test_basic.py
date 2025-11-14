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
cls;
let x = 5;
let y = 10;
print(x + y);

let arr = [1, 2, 3];
let d = { "a": 1, "b": 2 };
print(arr[1]);
print(d["b"]);

if x < y {
    print(100);
} else {
    print(200);
}

while x < 10 {
    x = x + 1;
    if x == 7 {
        break;
    }
    continue;
}

for i = 0 to 3 {
    print(i);
}

fn add(a, b) {
    return a + b;
}

print(add(2, 3));
return 42;
""")
    out = capture_run(str(p))
    # expected: y = 10 and 11 from the second print
    assert "10" in out
    assert "11" in out
