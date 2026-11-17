"""计算器工具。

大模型做算术不可靠，文档里一旦涉及金额、比例、汇总就容易被算错；
这里用 AST 白名单求值，只允许四则运算、幂、括号和少量数学函数，
不用 eval，避免代码注入。
"""

import ast
import math
import operator

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "pow": pow,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
}
_CONSTANTS = {"pi": math.pi, "e": math.e}

# 中文/全角符号归一化，用户和模型都可能写成全角
_NORMALIZE = str.maketrans(
    {"（": "(", "）": ")", "×": "*", "÷": "/", "－": "-", "﹙": "(", "﹚": ")"}
)


def _eval_node(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("只支持数字运算")
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
            raise ValueError("不支持的函数")
        return _FUNCTIONS[node.func.id](*[_eval_node(arg) for arg in node.args])
    raise ValueError("表达式只支持数字、四则运算、幂、括号和常用数学函数")


class Calculator:
    inputs: str = "数学表达式，例如 (128+256)*0.5"

    def run(self, expression):
        expression = (expression or "").strip().strip('"').strip("'").split("\n")[0]
        expression = expression.replace(",", "").translate(_NORMALIZE).strip()
        if not expression:
            return "calculator 需要输入一个数学表达式"

        try:
            result = _eval_node(ast.parse(expression, mode="eval").body)
        except ZeroDivisionError:
            return "计算失败：除数不能为 0"
        except Exception as e:
            return f"计算失败：{e}"

        if isinstance(result, float) and result.is_integer() and abs(result) < 1e16:
            result = int(result)
        elif isinstance(result, float):
            result = round(result, 10)
        return f"{expression} = {result}"


calculator = Calculator()
