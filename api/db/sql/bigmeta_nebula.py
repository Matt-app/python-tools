QUERY_COLUMN_UPSTREAM_COLUMN = '''
MATCH (src:column)-[cip:column_input_process]->(mid:process)-[poc:process_output_column]->(dst:column) 
WHERE id(dst) in $guid_list 
RETURN src, mid, dst; 
'''