QUERY_COLUMN_LIST = '''
    select guid from bigmeta_entity_column bec
    where bec.is_deleted= 0
    order by guid_hash
    offset %s
    limit %s;
    '''
QUERY_UPSTREAM_COLUMN_LIST = '''
    select upstream_columns from mlas_column_lineage bec
    where dst_column_guid = %s;
    '''
INSERT_COLUMN_LINEAGE = '''
    insert into mlas_column_lineage(upstream_columns, dst_column_guid) values(%s, %s);
    '''