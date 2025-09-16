QUERY_COLUMN_LIST = '''
    select column_guid from mlas_entity_column
    order by id
    limit %s, %s;
    '''
QUERY_UPSTREAM_COLUMN_LIST = '''
    select upstream_columns from mlas_lineage_column
    where dst_column_guid = %s;
    '''

# 批量查询多个目标列的上游血缘，需在执行前用占位符列表格式化 {placeholders}
QUERY_UPSTREAM_COLUMN_LIST_BATCH = '''
    select dst_column_guid, upstream_columns from mlas_lineage_column
    where dst_column_guid in ({placeholders});
    '''

QUERY_TAB_GUID = '''
    select C3 as table_guid, C11 as table_type from bigmeta_entity_table
    where C30 = '0';
    '''

INSERT_COLUMN_LINEAGE = '''
    insert into mlas_lineage_column(upstream_columns, dst_column_guid) 
    values(%s, %s)
    on duplicate key update
    upstream_columns = values(upstream_columns);
    '''

INIT_COLUMN_GUID = '''
    insert into mlas_entity_column(column_guid) values(%s);
    '''
