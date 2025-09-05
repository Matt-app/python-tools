# 使用 GO FROM 代替 MATCH，查询列上游关系
# 结果列：src, mid, dst
# 注意：Nebula 不支持在 GO FROM 的 VID 列表处使用参数，因此需在执行器中内联组装 {guid_list}

QUERY_COLUMN_UPSTREAM_COLUMN = '''
GO FROM {guid_list} OVER process_output_column REVERSELY 
YIELD id($^) AS dst, id($$) AS mid |
GO FROM $-.mid OVER column_input_process REVERSELY 
YIELD id($$) AS src, $-.mid AS mid, $-.dst AS dst
'''

TEST = '''
MATCH (v:<tag_name>) RETURN v LIMIT 10;
'''

