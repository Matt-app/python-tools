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

    def insert_column_lineage(self, data):
        from api.db.sql import SQL_INSERT_COLUMN_LINEAGE
        self.db_connector.execute_batch_script_no_fetch(SQL_INSERT_COLUMN_LINEAGE, data)


class SQLExecutorTest:
    """简单测试类，用于本地验证 SQLExecutor 的关键方法。"""
    def __init__(self, db_type):
        self.executor = SQLExecutor(db_type)

    def test_query_column_guid_list(self):
        gen = self.executor.query_column_guid_list(total=10, limit=5, offset=0)
        first = next(gen, None)
        print('query_column_guid_list first batch:', first)
        return first

    def test_query_upstream_column_guid_list(self, guid):
        res = self.executor.query_upstream_column_guid_list(guid)
        print('query_upstream_column_guid_list:', res)
        return res

    def test_insert_column_lineage(self):
        # 仅做接口连通性演示，不实际写入
        payload = [("a,b", "c")]
        try:
            self.executor.insert_column_lineage(payload)
            print('insert_column_lineage executed')
        except Exception as e:
            print('insert_column_lineage error:', e)


if __name__ == '__main__':
    # 示例：按需替换为 POSTGRESQL/MYSQL 并补充 guid 值
    tester = SQLExecutorTest('POSTGRESQL')
    tester.test_query_column_guid_list()
    # tester.test_query_upstream_column_guid_list('<some-guid>')
    # tester.test_insert_column_lineage()
