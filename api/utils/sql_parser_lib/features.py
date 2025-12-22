from typing import Any, Dict, List, Optional
from sqlglot import exp


def _extract_functions_and_ops(node: exp.Expression) -> Dict[str, List[Dict[str, Any]]]:
    """提取函数、运算符、窗口函数、CASE、CAST、常见条件函数等信息。

    返回结构：
    {
        "functions": [{name, args_count, distinct, position}],
        "operators": [{op, position}],
        "window_functions": [{name, partition_by, order_by, position}],
        "case_expressions": [{branches_count, has_else, position}],
        "cast_expressions": [{from_type, to_type, position}],
        "conditional_functions": [{name, args_count, position}],
    }
    """
    funcs: List[Dict[str, Any]] = []
    ops: List[Dict[str, Any]] = []
    window_funcs: List[Dict[str, Any]] = []
    case_exprs: List[Dict[str, Any]] = []
    cast_exprs: List[Dict[str, Any]] = []
    conditional_funcs: List[Dict[str, Any]] = []

    cond_names = {"NVL", "NVL2", "ISNULL", "COALESCE", "NULLIF", "GREATEST", "LEAST", "DECODE"}

    def add_func(fn: exp.Expression, position: Optional[str] = None):
        name = (getattr(fn, "key", None) or fn.__class__.__name__ or "").upper()
        args_cnt = 0
        for v in (getattr(fn, args, {}) or {}).values():
            if isinstance(v, list):
                args_cnt += len(v)
            elif isinstance(v, exp.Expression):
                args_cnt += 1
        funcs.append({
            "name": name,
            "args_count": args_cnt,
            "distinct": bool(getattr(fn, "is_distinct", False)),
            "position": position,
        })

    def add_window(w: exp.Window, position: Optional[str] = None):
        fname = ""
        if getattr(w, "this", None):
            fname = getattr(w.this, "key", w.this.__class__.__name__).upper()
        part_cols: List[str] = []
        if getattr(w, "partition_by", None):
            for c in w.partition_by:
                try:
                    part_cols.append(c.sql())
                except Exception:
                    part_cols.append(str(c))
        order_cols: List[str] = []
        if getattr(w, "order", None):
            for c in (w.order.expressions or []):
                try:
                    order_cols.append(c.sql())
                except Exception:
                    order_cols.append(str(c))
        window_funcs.append({
            "name": fname,
            "partition_by": part_cols,
            "order_by": order_cols,
            "position": position,
        })

    def add_case(c: exp.Case, position: Optional[str] = None):
        case_exprs.append({
            "branches_count": len(getattr(c, "ifs", []) or []),
            "has_else": bool(getattr(c, "default", None)),
            "position": position,
        })

    def add_cast(c: exp.Cast, position: Optional[str] = None):
        to_type = str(getattr(c, "to", "UNKNOWN"))
        src = getattr(c, "this", None)
        if isinstance(src, exp.Literal):
            from_type = "LITERAL"
        elif isinstance(src, exp.Column):
            from_type = "COLUMN"
        elif isinstance(src, exp.Expression):
            from_type = "EXPRESSION"
        else:
            from_type = "UNKNOWN"
        cast_exprs.append({
            "from_type": from_type,
            "to_type": to_type,
            "position": position,
        })

    def add_conditional(fn: exp.Expression, position: Optional[str] = None):
        name = (getattr(fn, "key", None) or fn.__class__.__name__ or "").upper()
        args_cnt = 0
        for v in (getattr(fn, args, {}) or {}).values():
            if isinstance(v, list):
                args_cnt += len(v)
            elif isinstance(v, exp.Expression):
                args_cnt += 1
        conditional_funcs.append({
            "name": name,
            "args_count": args_cnt,
            "position": position,
        })

    def add_op(symbol: str, position: Optional[str] = None):
        ops.append({"op": symbol, "position": position})

    stack: List[exp.Expression] = [node]
    while stack:
        cur = stack.pop()

        # Functions and variants
        if isinstance(cur, exp.Window):
            add_window(cur)
        elif isinstance(cur, exp.Case):
            add_case(cur)
        elif isinstance(cur, exp.Cast):
            add_cast(cur)
        elif isinstance(cur, (exp.Coalesce, exp.Nullif)):
            add_conditional(cur)
        elif isinstance(cur, exp.Func):
            key = (getattr(cur, "key", "") or "").upper()
            if key in cond_names:
                add_conditional(cur)
            else:
                add_func(cur)

        # Operators
        if isinstance(cur, exp.Add):
            add_op("+")
        elif isinstance(cur, exp.Sub):
            add_op("-")
        elif isinstance(cur, exp.Mul):
            add_op("*")
        elif isinstance(cur, exp.Div):
            add_op("/")
        elif isinstance(cur, exp.Mod):
            add_op("%")
        elif isinstance(cur, exp.And):
            add_op("AND")
        elif isinstance(cur, exp.Or):
            add_op("OR")
        elif isinstance(cur, exp.Not):
            add_op("NOT")
        elif isinstance(cur, exp.EQ):
            add_op("=")
        elif isinstance(cur, exp.NEQ):
            add_op("!=")
        elif isinstance(cur, exp.GT):
            add_op(">")
        elif isinstance(cur, exp.GTE):
            add_op(">=")
        elif isinstance(cur, exp.LT):
            add_op("<")
        elif isinstance(cur, exp.LTE):
            add_op("<=")
        elif isinstance(cur, exp.Like):
            add_op("LIKE")
        elif isinstance(cur, exp.ILike):
            add_op("ILIKE")
        elif isinstance(cur, exp.In):
            add_op("IN")
        elif isinstance(cur, exp.Between):
            add_op("BETWEEN")
        elif isinstance(cur, exp.Is):
            add_op("IS")
        elif isinstance(cur, exp.Exists):
            add_op("EXISTS")

        # Traverse children
        for child in cur.args.values():
            if isinstance(child, list):
                for c in child:
                    if isinstance(c, exp.Expression):
                        stack.append(c)
            elif isinstance(child, exp.Expression):
                stack.append(child)

    return {
        "functions": funcs,
        "operators": ops,
        "window_functions": window_funcs,
        "case_expressions": case_exprs,
        "cast_expressions": cast_exprs,
        "conditional_functions": conditional_funcs,
    }
