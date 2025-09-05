QUERY_COLUMN_UPSTREAM_COLUMN = '''
-- 使用 GO FROM 代替 MATCH，查询列上游关系
-- 参数：$guid_list (list<string>) 顶点ID列表
-- 结果列：src, mid, dst
GO FROM $guid_list OVER process_output_column REVERSELY 
YIELD id($^) AS dst, id($$) AS mid |
GO FROM $-.mid OVER column_input_process REVERSELY 
YIELD id($$) AS src, $-.mid AS mid, $-.dst AS dst
'''