from typing import Any, Dict, List
from sqlglot import exp


def _collect_referenced_columns(node: exp.Expression) -> List[str]:
    """收集表达式中引用到的列名（含可能的表/别名前缀）。"""
    cols: List[str] = []
    stack: List[exp.Expression] = [node]
    seen: set = set()
    while stack:
        cur = stack.pop()
        if isinstance(cur, exp.Column):
            try:
                col_sql = cur.sql(pretty=False)
            except Exception:
                col_sql = str(cur)
            if col_sql not in seen:
                seen.add(col_sql)
                cols.append(col_sql)
        for child in cur.args.values():
            if isinstance(child, list):
                stack.extend([c for c in child if isinstance(c, exp.Expression)])
            elif isinstance(child, exp.Expression):
                stack.append(child)
    return cols


def _extract_column_lineage(node: exp.Expression) -> Dict[str, List[str]]:
    """粗粒度的字段血缘：
    - referenced_columns: 当前节点语法树中出现的列名集合
    - derived_columns: 针对 SELECT 投影，给出别名->来源列集合（若存在）
    """
    referenced: List[str] = _collect_referenced_columns(node)
    derived: Dict[str, List[str]] = {}

    # 针对 SELECT 投影
    q = node if isinstance(node, exp.Select) else node.find(exp.Select)
    if q is not None:
        for proj in q.expressions:
            alias_name = None
            base_expr = proj
            if isinstance(proj, exp.Alias):
                alias_name = getattr(proj, alias, None) or (proj.alias_or_name if hasattr(proj, alias_or_name) else None)
                base_expr = proj.this
            elif isinstance(proj, exp.Column):
                alias_name = proj.name
                base_expr = proj
            if alias_name:
                derived[alias_name] = _collect_referenced_columns(base_expr)

    return {"referenced_columns": referenced, "derived_columns": derived}
