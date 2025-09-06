QUERY_COLUMN_LIST = '''
    select column_guid from mlas_entity_column
    order by id
    limit %s, %s;
    '''
QUERY_UPSTREAM_COLUMN_LIST = '''
    select upstream_columns from mlas_lineage_column bec
    where dst_column_guid = %s;
    '''
INSERT_COLUMN_LINEAGE = '''
    insert into mlas_lineage_column(upstream_columns, dst_column_guid) values(%s, %s);
    '''

INIT_COLUMN_GUID = '''
    insert into mlas_entity_column(column_guid) values(%s);
    '''
