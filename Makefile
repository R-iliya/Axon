
---

## `Makefile`
```makefile
.PHONY: run repl test

run:
	python -m axon.run examples/hello.ax

repl:
	python -m axon.repl

test:
	pytest -q
