import argparse
import ast
import operator
import sys


def parse_arguments(raw_args: list[str]) -> argparse.Namespace:
    print(f"[math_tool.py][parse_arguments] raw_args={raw_args}")
    parser = argparse.ArgumentParser(description="Evaluate a mathematical expression.")
    parser.add_argument(
        "--expression",
        "-e",
        required=True,
        help="Mathematical expression to evaluate.",
    )
    namespace = parser.parse_args(raw_args)
    print(f"[math_tool.py][parse_arguments] namespace={namespace}")
    return namespace


def evaluate_expression(expression: str) -> float:
    print(f"[math_tool.py][evaluate_expression] expression={expression}")
    node = ast.parse(expression, mode="eval")
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
    }

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.BinOp) and type(node.op) in operators:
            return operators[type(node.op)](_eval(node.left), _eval(node.right))
        raise ValueError("Unsupported expression")

    result = _eval(node)
    print(f"[math_tool.py][evaluate_expression] result={result}")
    return result


def main():
    raw_args = sys.argv[1:]
    print(f"[math_tool.py][main] raw_args={raw_args}")
    namespace = parse_arguments(raw_args)
    expression = namespace.expression
    value = evaluate_expression(expression)
    print(value)
    print(f"[math_tool.py][main] expression={expression}, value={value}")


if __name__ == "__main__":
    main()
