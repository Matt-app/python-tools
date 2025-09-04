import logging
import traceback
from collections import namedtuple

import psycopg
from psycopg_pool import ConnectionPool
import contextlib

from api.log import logger


class PostgresConnector:
    """
    数据库链接
    """
    def __init__(self, min_conn, max_conn, database, user, password, host, port):
        self.pool = self._create_pool(
            min_conn=min_conn,
            max_conn=max_conn,
            database=database,
            user=user,
            password=password,
            host=host,
            port=port
        )

    def _create_pool(self, min_conn, max_conn, database, user, password, host, port):
        """创建并配置连接池"""
        # 构建连接字符串
        conn_info = f"""
            dbname={database}
            user={user}
            password={password}
            host={host}
            port={port}
        """

        # 创建连接池
        pool = ConnectionPool(
            conninfo=conn_info,
            min_size=min_conn,
            max_size=max_conn,
            # 连接超时时间（秒）
            timeout=10,
            # 连接最大空闲时间（秒）
            max_idle=300,
            # 连接回收时间（秒）
            max_lifetime=3600,
            # 连接名（用于监控）
            name="mlas-pool"
        )

        # 预先打开最小连接数
        pool.wait(5.0)  # 等待最多5秒建立初始连接
        return pool

    @contextlib.contextmanager
    def _get_connection(self):
        """上下文管理器，用于获取和自动归还连接"""
        def _log_query_conn():
            def listener(msg):
                if msg.code == psycopg.pq.ExecStatus.COMMAND_OK:
                    logger.info('execute sql: %s', msg.query)
            conn.add_notice_handler(listener)
            return conn
        conn = self.pool.getconn()
        log_conn = _log_query_conn()
        try:
            yield log_conn
        finally:
            self.pool.putconn(conn)

    def execute_script_no_fetch(self, script: str, values=None):
        """
        执行无查询结果sql，返回影响行数
        :param script: 脚本内容
        :param values: 参数
        :return: 影响行数
        """
        with self._get_connection() as pg_conn:
            try:
                with pg_conn.cursor() as cursor:
                    cursor.execute(script, values)

                    pg_conn.commit()
                    return cursor.rowcount
            except Exception as e:
                logging.error('Error execution script, values: %s; script: %s', values, script)
                traceback.print_exc()
                return 0

    def execute_batch_script_no_fetch(self, script: str, values=None):
        """
        批量执行无查询结果sql，返回影响行数
        :param script: 脚本内容
        :param values: 参数
        :return: 影响行数
        """
        with self._get_connection() as pg_conn:
            try:
                with pg_conn.cursor() as cursor:
                    cursor.executemany(script, values)
                    pg_conn.commit()
                    return cursor.rowcount
            except Exception as e:
                logging.error('Error execution script: %s', e)
                return 0

    def execute_stream_script(self, script: str, values=None):

        def _batch_fetch(batch_size=5000):
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                yield from (query_result(*x) for x in rows)

        with self._get_connection() as pg_conn:
            try:
                with pg_conn.cursor() as cursor:
                    cursor.execute(script, values)
                    pg_conn.commit()
                    column_names = [x[0] for x in cursor.description]
                    query_result = namedtuple('query_result', column_names)
                    r = _batch_fetch()
                    yield from r
            except Exception as e:
                logging.error('Error execution script: %s', e)
                yield 0

    def execute_script(self, script: str, values=None):
        """
        执行SQL，返回查询结果
        :param script: 脚本内容
        :param values: 参数
        :return: 查询结果
        """
        with self._get_connection() as pg_conn:
            try:
                with pg_conn.cursor() as cursor:
                    cursor.execute(script, values)
                    pg_conn.commit()
                    column_names = [x[0] for x in cursor.description]
                    r = cursor.fetchall()
                    query_result = namedtuple('query_result', column_names)
                    return [query_result(*x) for x in r]
            except Exception as e:
                logging.error('Error execution script, values: %s; script: %s', values, script)
                traceback.print_exc()
                return 0

    def update_value_by_conditions(self, table: str, column_names: list,
                                            where_conditions: list, values: tuple):
        """
        有则更新，无则新增
        :param table: 表名
        :param column_names: 更新列名
        :param where_conditions: 更新条件
        :param values: 参数
        :return: 1成功；0失败
        """
        try:
            columns = ', '.join(f'{x} = %s' for x in column_names)
            conditions = ' AND '.join(f'{x} = %s' for x in where_conditions)
            script = f'UPDATE {table} SET {columns}'
            script = script + f' WHERE {conditions};' if conditions else script + ';'
            rowcount = self.execute_script_mysql_no_fetch(script, values)
            if rowcount == 0:
                columns = ', '.join(column_names + where_conditions)
                values_s = ', '.join(['%s'] * len(values))
                script = f'INSERT INTO {table} ({columns}) VALUES ({values_s});'
                self.execute_script_mysql_no_fetch(script, values)
            return 1
        except Exception as e:
            logging.error('Error execution script: %s', e)
            return 0


