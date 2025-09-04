import logging
from collections import namedtuple

from psycopg2 import pool


class DBUtils:
    """
    数据库链接
    """
    PASSWORD = '1qaz!QAZ'
    HOST = '10.126.158.203'
    USER = 'aloudata'
    DATABASE = 'bigmeta'
    PORT = '5432'
    MIN_CONN = 1
    MAX_CONN = 10

    def __init__(self):
        self.pg_connection_pool = pool.SimpleConnectionPool(
            minconn=self.MIN_CONN, maxconn=self.MAX_CONN, dbname=self.DATABASE, user=self.USER, password=self.PASSWORD,
            host=self.HOST, port=self.PORT
        )

    def _get_pg_connection(self):
        try:
            return self.pg_connection_pool.getconn()
        except Exception as e:
            logging.error('Error getting connection from pool: %s', e)
            return

    def _release_pg_connection(self, conn):
        try:
            self.pg_connection_pool.putconn(conn)
        except Exception as e:
            logging.error('Error returning connection to pool: %s', e)
            return

    def execute_script_postgres_no_fetch(self, script: str, values=None):
        """
        执行无查询结果sql，返回影响行数
        :param script: 脚本内容
        :param values: 参数
        :return: 影响行数
        """
        pg_conn = self._get_pg_connection()
        try:
            with pg_conn.cursor() as cursor:
                cursor.execute(script, values)
                pg_conn.commit()
                return cursor.rowcount
        except Exception as e:
            logging.error('Error execution script: %s', e)
            return 0
        finally:
            self._release_pg_connection(pg_conn)

    def execute_batch_script_postgres_no_fetch(self, script: str, values=None):
        """
        批量执行无查询结果sql，返回影响行数
        :param script: 脚本内容
        :param values: 参数
        :return: 影响行数
        """
        pg_conn = self._get_pg_connection()
        try:
            with pg_conn.cursor() as cursor:
                cursor.executemany(script, values)
                pg_conn.commit()
                return cursor.rowcount
        except Exception as e:
            logging.error('Error execution script: %s', e)
            return 0
        finally:
            self._release_pg_connection(pg_conn)

    def execute_stream_script_postgres(self, script: str, values=None):
        def _batch_fetch(batch_size=5000):
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                yield from (query_result(*x) for x in rows)

        pg_conn = self._get_pg_connection()
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
        finally:
            self._release_pg_connection(pg_conn)
        # 使用生成器避免全量加载内存

    def execute_script_postgres(self, script: str, values=None):
        """
        执行SQL，返回查询结果
        :param script: 脚本内容
        :param values: 参数
        :return: 查询结果
        """
        pg_conn = self._get_pg_connection()
        try:
            with pg_conn.cursor() as cursor:
                cursor.execute(script, values)
                pg_conn.commit()
                column_names = [x[0] for x in cursor.description]
                r = cursor.fetchall()
                query_result = namedtuple('query_result', column_names)
                return [query_result(*x) for x in r]
        except Exception as e:
            logging.error('Error execution script: %s', e)
            return 0
        finally:
            self._release_pg_connection(pg_conn)

    def update_value_postgres_by_conditions(self, table: str, column_names: list,
                                            where_conditions: list, values: tuple):
        """
        有则更新，无则新增
        :param table: 表名
        :param column_names: 更新列名
        :param where_conditions: 更新条件
        :param values: 参数
        :return: 1成功；0失败
        """
        pg_conn = self._get_pg_connection()
        try:
            columns = ', '.join(f'{x} = %s' for x in column_names)
            conditions = ' AND '.join(f'{x} = %s' for x in where_conditions)
            script = f'UPDATE {table} SET {columns}'
            script = script + f' WHERE {conditions};' if conditions else script + ';'
            rowcount = self.execute_script_postgres_no_fetch(script, values)
            if rowcount == 0:
                columns = ', '.join(column_names + where_conditions)
                values_s = ', '.join(['%s'] * len(values))
                script = f'INSERT INTO {table} ({columns}) VALUES ({values_s});'
                self.execute_script_postgres_no_fetch(script, values)
            return 1
        except Exception as e:
            logging.error('Error execution script: %s', e)
            return 0
        finally:
            self._release_pg_connection(pg_conn)


class FormatRelation:
    def __init__(self):
        self.gp_conn = DBUtils()
        self.table_relations = set()
        column_names = [
            'src_datasource', 'src_database', 'src_schema', 'src_table', 'dst_datasource', 'dst_database', 'dst_schema',
            'dst_table']
        self.TABLE_RELATION = namedtuple('table_relation', column_names)
        self.query_table_relation_script = '''
        select table_relations 
        from bigmeta_entity_task 
        where is_deleted = 0 and table_relations is not null;
        '''
        self.insert_table_relation_script = '''
        INSERT INTO mcd_table_relations
        (src_datasource, src_database, src_schema, src_table, dst_datasource, dst_database, dst_schema, dst_table)
        VALUES(%s, %s, %s, %s, %s, %s, %s, %s);
        '''

    def get_table_relations(self):
        relation_data = self.gp_conn.execute_stream_script_postgres(self.query_table_relation_script)
        for i in relation_data:
            for table_relation in i.table_relations:
                for input_table in table_relation['inputTableGuids']:
                    self.table_relations.add(
                        self.TABLE_RELATION(
                            *input_table.split('.')[1:], *table_relation['outputTableGuid'].split('.')[1:]
                        )
                    )

    def export_to_pg(self, batch_num=1000):
        self.table_relations = list(self.table_relations)
        n = len(self.table_relations)
        logging.error('total: %s', n)
        for i in range(n//batch_num+1):
            r = self.gp_conn.execute_batch_script_postgres_no_fetch(
                self.insert_table_relation_script, self.table_relations[batch_num*i: batch_num*(1+i)])
            logging.error('num: %s', r)


if __name__ == "__main__":
    fr = FormatRelation()
    fr.get_table_relations()
    fr.export_to_pg()
