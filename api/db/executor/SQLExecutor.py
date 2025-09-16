from api.db.connector.MysqlConnector import MysqlConnector
from api.db.connector.PostgresConnector import PostgresConnector
from api.log import logger
from api.conf.config import PG_CONFIG, MYSQL_CONFIG


class SQLExecutor:
    def __init__(self, db_type):
        """

        :param db_type: POSTGRESQL/MYSQL
        """
        if db_type == 'POSTGRESQL':
            self.db_connector = PostgresConnector(PG_CONFIG['MIN_CONN'], PG_CONFIG['MAX_CONN'], PG_CONFIG['DATABASE'],
                                                  PG_CONFIG['USER'], PG_CONFIG['PASSWORD'], PG_CONFIG['HOST'],
                                                  PG_CONFIG['PORT'])
        elif db_type == 'MYSQL':
            self.db_connector = MysqlConnector(MYSQL_CONFIG['MIN_CONN'], MYSQL_CONFIG['MAX_CONN'],
                                               MYSQL_CONFIG['DATABASE'],
                                               MYSQL_CONFIG['USER'], MYSQL_CONFIG['PASSWORD'], MYSQL_CONFIG['HOST'],
                                               MYSQL_CONFIG['PORT'], MYSQL_CONFIG['CHARSET'], MYSQL_CONFIG['COLLATION'])
        logger.info('SQLExecutor init')

    def query_column_guid_list(self, total, limit, offset):
        from api.db.sql import SQL_QUERY_COLUMN_LIST
        for n in range(total // limit + 1):
            yield self.db_connector.execute_script(SQL_QUERY_COLUMN_LIST, (offset, limit))
            offset += limit

    def query_upstream_column_guid_list(self, guid):
        from api.db.sql import SQL_QUERY_UPSTREAM_COLUMN_LIST
        # 传入单个 guid，注意占位符为 %s
        return self.db_connector.execute_script(SQL_QUERY_UPSTREAM_COLUMN_LIST, (guid,))

    def query_upstream_column_guid_list_batch(self, guids):
        """
        批量查询多个目标列的上游血缘
        :param guids: list[str]
        :return: 查询结果列表，每行包含 dst_column_guid, upstream_columns
        """
        if not guids:
            return []
        from api.db.sql import SQL_QUERY_UPSTREAM_COLUMN_LIST_BATCH
        placeholders = ','.join(['%s'] * len(guids))
        sql = SQL_QUERY_UPSTREAM_COLUMN_LIST_BATCH.format(placeholders=placeholders)
        return self.db_connector.execute_script(sql, tuple(guids))

    def query_table_guid_list(self):
        from api.db.sql import SQL_QUERY_TAB_GUID
        return self.db_connector.execute_script(SQL_QUERY_TAB_GUID)

    def insert_column_lineage(self, data):
        from api.db.sql import SQL_INSERT_COLUMN_LINEAGE
        self.db_connector.execute_batch_script_no_fetch(SQL_INSERT_COLUMN_LINEAGE, data)

    def init_column_guid(self, data):
        from api.db.sql import SQL_INIT_COLUMN_GUID
        self.db_connector.execute_batch_script_no_fetch(SQL_INIT_COLUMN_GUID, data)



