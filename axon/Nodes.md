# 🧠 Axon Nodes — Full Documentation

---

### 🧮 **Expressions**

These evaluate to values — numbers, strings, booleans, lists, etc.

* **NumberNode**

  * `let x = 5;` → stores the number `5`.

* **StringNode**

  * `let name = "Axon";` → stores `"Axon"`.

* **BooleanNode**

  * `let flag = True;` → stores `True`.

* **VariableNode**

  * `print(x);` → retrieves the value of `x`.

* **BinOpNode**

  * `3 + 4 * 2;` → evaluates math or logic expressions.

* **UnaryOpNode**

  * `-x` or `not y;` → negation or boolean inversion.

* **ListNode**

  * `[1, 2, 3];` → creates a list.

* **IndexNode**

  * `arr[1];` → accesses list element by index.

* **DictNode**

  * `{"name": "Axon", "version": 1};` → creates a dictionary.

---

### 📜 **Statements**

They perform actions or control how the program flows.

* **PrintNode**

  * `print("hello");` → outputs “hello”.

* **LetNode**

  * `let x = 10;` → defines a variable.

* **ClearNode**

  * `clear();` → clears terminal screen.

* **IfNode**

  * ```
    if x > 0 {
      print("positive");
    } else {
      print("non-positive");
    }
    ```

* **WhileNode**

  * ```
    while x < 5 {
      print(x);
      let x = x + 1;
    }
    ```

* **ForNode**

  * ```
    for i = 0 to 3 {
      print(i);
    }
    ```

* **BreakNode**

  * ```
    while true {
      break;
    }
    ```

* **ContinueNode**

  * ```
    for i = 0 to 5 {
      if i == 2 { continue; }
      print(i);
    }
    ```

* **BreakException / ContinueException**

  * internal exceptions used by `BreakNode` and `ContinueNode`.

---

### ⚙️ **Functions**

Nodes that define, call, or return from functions.

* **FunctionNode**

  * ```
    func greet(name) {
      print("Hello " + name);
    }
    ```

* **CallNode**

  * `greet("Axon");` → executes the function.

* **ReturnNode**

  * ```
    func square(x) {
      return x * x;
    }
    ```

---
