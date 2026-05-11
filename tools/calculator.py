import math


async def calculator(expression: str) -> str:
    """安全的數學計算工具，支援 math 模組中的函數。"""
    safe_globals = {
        "__builtins__": {},
        **{k: getattr(math, k) for k in dir(math) if not k.startswith("_")},
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "pow": pow,
    }
    try:
        result = eval(expression, safe_globals)
        return str(result)
    except ZeroDivisionError:
        return "計算錯誤：除以零"
    except Exception as e:
        return f"計算錯誤：{e}"
