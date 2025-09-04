import traceback
from collections import namedtuple

from mysql.connector import pooling

from api.log import logger


class MysqlConnector:
    """
    数据库链接
    """

    def __init__(self, min_conn, max_conn, database, user, password, host, port, charset, collation, connection_timeout=None):
        # 仅传递 mysql-connector 支持的关键字
        self.pool = self._create_pool(
            min_conn=min_conn,
            max_conn=max_conn,
            database=database,
            user=user,
            password=password,
            host=host,
            port=int(port) if port is not None else None,
            charset=charset,
            connection_timeout=connection_timeout
        )

    def _create_pool(self, min_conn, max_conn, **kwargs):
        """创建MySQL连接池"""
        allowed_keys = {"host", "database", "user", "password", "port", "charset", "connection_timeout"}
        conn_kwargs = {k: v for k, v in kwargs.items() if k in allowed_keys and v is not None}
        pool_config = {
            "pool_name": "mlas_pool",
            "pool_size": max_conn,  # 最大连接数
            "pool_reset_session": True,
            **conn_kwargs
        }

        # 创建连接池
        pool = pooling.MySQLConnectionPool(**pool_config)
        return pool

    def _get_connection(self):
        """从池中获取连接"""
        return self.pool.get_connection()

    def execute_script_no_fetch(self, script: str, values=None):
        """
        执行无查询结果sql，返回影响行数
        :param script: 脚本内容
        :param values: 参数
        :return: 影响行数
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute(script, values)
                    conn.commit()
                    logger.info('execute sql: %s', cursor.statement)
                    return cursor.rowcount
                except Exception as e:
                    logger.error('Error execution script, values: %s; script: %s', values, script)
                    traceback.print_exc()
                    return 0

    def execute_batch_script_no_fetch(self, script: str, values=None):
        """
        批量执行无查询结果sql，返回影响行数
        :param script: 脚本内容
        :param values: 参数
        :return: 影响行数
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.executemany(script, values)
                    conn.commit()
                    logger.info('execute sql: %s', cursor.statement)
                    return cursor.rowcount
                except Exception as e:
                    logger.error('Error execution script, values: %s; script: %s', values, script)
                    traceback.print_exc()
                    return 0

    def execute_stream_script(self, script: str, values=None):
        def _batch_fetch(batch_size=5000):
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                yield from (query_result(*x) for x in rows)

        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute(script, values)
                    logger.info('execute sql: %s', cursor.statement)
                    column_names = [x[0] for x in cursor.description]
                    query_result = namedtuple('query_result', column_names)
                    r = _batch_fetch()
                    yield from r
                except Exception as e:
                    logger.error('Error execution script, values: %s; script: %s', values, script)
                    traceback.print_exc()
                    yield None
        # 使用生成器避免全量加载内存

    def execute_script(self, script: str, values=None):
        """
        执行SQL，返回查询结果
        :param script: 脚本内容
        :param values: 参数
        :return: 查询结果
        """
        with self._get_connection() as conn:

            with conn.cursor() as cursor:
                try:
                    cursor.execute(script, values)
                    logger.info('execute sql: %s', cursor.statement)
                    column_names = [x[0] for x in cursor.description]
                    r = cursor.fetchall()
                    query_result = namedtuple('query_result', column_names)
                    return [query_result(*x) for x in r]
                except Exception as e:
                    logger.error('Error execution script, values: %s; script: %s', values, script)
                    traceback.print_exc()
                    return []

