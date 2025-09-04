import json
import logging
import os.path
import time
from collections import namedtuple
from concurrent.futures import ProcessPoolExecutor
from typing import Generator

import requests
from psycopg2 import pool


class DBConnect:
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


class ImpactAnalysis:
    """
    影响分析
    """
    USERNAME = 'admin'
    PASSWORD = '9d86d8f1'

    DOMAIN = 'http://bigmeta.dataapi.mcdonalds.cn/'
    # DOMAIN = 'http://bigmeta-dev.mcdonalds.cn:8080/'
    API_ID = 'APP_1'
    API_Token = '9df95b42-2130-473f-a912-e0a71fe6d98e'
    # API_Token = '26cdf7ff-bafe-4b38-9c6e-ac5d3c127912'
    LOGIN = 'login'
    TASK_DETAILS = 'open/api/v1/task/details'
    TAB_DETAILS = 'open/api/v1/table/details'
    CUSTOM_DETAILS = 'open/api/v1/custom/details'
    TASK_OVERVIEW = 'asset/task/overview'
    TAB_OVERVIEW = 'asset/table/overview'
    COL_RELATIONS = 'open/api/v1/column/relations'
    TAB_RELATIONS = 'open/api/v1/table/relations'
    CUSTOM_RELATIONS = 'open/api/v1/custom/relations'
    SCRIPT_EXTRACT = 'open/api/v1/reltable/scriptExtract'
    # 在线模拟
    LINEAGE_SIMULATION_CREATE = 'simulation/task/create'
    LINEAGE_SIMULATION_RELATION = 'simulation/task/relation'
    LINEAGE_SIMULATION_COLUMNS = 'simulation/task/columns'
    LINEAGE_SIMULATION_ERROR_INFO = 'simulation/task/errorInfo'
    # 血缘接口
    COLUMN_OVERVIEW = 'column/process//overview'
    V2 = 'lineage/custom/v2'

    NODE_INFO = ['entityType', 'typeCode', 'guid']
    NODE_TUPLE = namedtuple('node', NODE_INFO)

    def __init__(self):
        self.script_dict = {}
        self.headers = {
            'Accept': 'application/json, text/plain, */*',
            'Bigmeta-Api-AppId': self.API_ID,
            'Bigmeta-Api-Token': self.API_Token
        }
        self._init_cookie(self.USERNAME, self.PASSWORD)
        self.db = DBConnect()

    def _init_cookie(self, username, password):
        data = {'username': username, 'password': password}
        r = requests.request('POST', self.DOMAIN + self.LOGIN, headers=self.headers, data=json.dumps(data))
        cookie = r.headers.get('Set-Cookie')
        self.headers['Cookie'] = cookie

    def _get_bigmeta_requests(self, url, param=None, params=None, method='GET') -> dict:
        """
        请求bigmeta服务
        :param url: 接口url
        :param param: GET普通参数/POST data参数
        :param params: GET params参数
        :param method: GET/POST
        :return: json格式
        """

        def _get():
            if method == 'POST':
                r_json = requests.request(method, self.DOMAIN + url, headers=self.headers,
                                          data=json.dumps(param)).json()
            elif params:
                r_json = requests.get(self.DOMAIN + url, params=params, headers=self.headers).json()
            elif param:
                r_json = requests.get(self.DOMAIN + url + param, headers=self.headers).json()
            else:
                raise {}
            success_mark = (r_json.get('code') == 'success' and
                            r_json.get('message') == 'success' and r_json.get('success', False))
            if success_mark:
                return r_json.copy()
            else:
                return {}

        try:
            return_value = _get()
        except:
            self._init_cookie(self.USERNAME, self.PASSWORD)
            return_value = _get()
        return return_value

    def get_output_tables(self, guid: str) -> list:
        """
        获取脚本输出表
        :param guid: 脚本guid
        :return: 输出表列表
        """
        r_json = self._get_bigmeta_requests(self.TASK_DETAILS, f'?guid={guid}')
        if r_json:
            output_tables = r_json.get('data', {}).get('outputTableGuids', [])
            return output_tables
        else:
            return []

    def get_table_overview(self, guid: str) -> dict:
        """
        获取表相关信息
        :param guid: 表guid
        :return:
        """
        r_json = self._get_bigmeta_requests(self.TAB_OVERVIEW, f'?guid={guid}')
        if r_json:
            output_tables = r_json.get('data', {})
            return output_tables
        else:
            return {}

    def get_table_tasks(self, guid: str) -> list:
        """
        获取表相关任务信息
        :param guid: 表guid
        :return:
        """
        overview = self.get_table_overview(guid)
        if overview:
            output_tasks = overview.get('tasks')
            return output_tasks
        else:
            return []

    def get_tables_columns(self, guid: str) -> list:
        """
        获取表的列
        :param guid: 表guid
        :return: 列列表
        """
        r_json = self._get_bigmeta_requests(self.TAB_DETAILS, f'?guid={guid}')
        if r_json:
            table_columns = [x['guid'] for x in r_json.get('data', {}).get('columns', [])]
            return table_columns
        else:
            return []

    def get_custom_info(self, guid: str) -> str:
        """
        获取列信息
        :param guid: 列guid
        :return: 列信息
        """
        r_json = self._get_bigmeta_requests(self.CUSTOM_DETAILS, f'?guid={guid}')
        if r_json:
            return r_json.get('data', {}).get('name', '')
        else:
            return ''

    def get_node_relations(self, entity_type: str, guid: str, direction='INPUT') -> list:
        """
        获取自定义实体血缘
        :param entity_type: TABLE-表/CUSTOM-自定义实体/COLUMN-列
        :param direction: INPUT-溯源/OUTPUT-扩散
        :param guid: 自定义实体guid
        :return: 血缘列表
        """
        if direction not in ['INPUT', 'OUTPUT']:
            raise Exception('ERROR: direction not in ("INPUT", "OUTPUT")')
        if entity_type not in ['TABLE', 'CUSTOM', 'COLUMN']:
            raise Exception('ERROR: entity_type not in ("TABLE", "CUSTOM", "COLUMN")')
        url_mapping = {'TABLE': self.TAB_RELATIONS, 'COLUMN': self.COL_RELATIONS, 'CUSTOM': self.CUSTOM_RELATIONS}
        r_json = self._get_bigmeta_requests(url_mapping[entity_type], f'?guid={guid}&direction={direction}')
        if r_json:
            output_direction = 'dstEntity' if direction == 'OUTPUT' else 'srcEntity'
            output_direction = 'dstEntity' if entity_type == 'TABLE' else output_direction
            output_relations = [self.NODE_TUPLE(x.get(output_direction, {})['entityType'],
                                                x.get(output_direction, {})['typeCode'],
                                                x.get(output_direction, {})['guid']) for x in r_json.get('data', {})]
            return output_relations.copy()
        else:
            return []

    def get_col_relations(self, guid: str):
        """
        获取列血缘
        :param guid: 列guid
        :return: 上游血缘
        """
        payload = json.dumps({
            "depth": 1,
            "direction": 'INPUT',
            "guids": [guid],
            "relations": ['ColumnDirectColumn'],
            "entityType": ['Column']}
        )
        headers = self.headers.copy()
        headers['Cookie'] = self.cookie
        r = requests.request("POST", self.DOMAIN + self.V2, headers=self.headers, data=payload)
        r_json = r.json()
        success_mark = (r_json.get('code') == 'success' and
                        r_json.get('message') == 'success' and r_json.get('success', False))
        if success_mark:
            col_relations = r_json.get('data', {}).get('relations', [])
            return col_relations
        return

    def get_task_col_relations(self, task_guid: str, col_guid: str):
        """
        获取列血缘
        :param guid: 列guid
        :return: 上游血缘
        """
        payload = json.dumps({
            "depth": 1,
            "direction": "INPUT",
            "guids": [
                col_guid
            ],
            "relations": [
                "ColumnDirectColumn"
            ],
            "entityType": "Column",
            "needIndirect": False,
            "taskGuid": task_guid
        }
        )
        r = requests.request("POST", self.DOMAIN + self.V2, headers=self.headers, data=payload)
        r_json = r.json()
        success_mark = (r_json.get('code') == 'success' and
                        r_json.get('message') == 'success' and r_json.get('success', False))
        if success_mark:
            col_relations = r_json.get('data', {}).get('relations', [])
            return col_relations
        return {}

    def get_col_overview(self, guid: str) -> dict:
        """
        获取表相关信息
        :param guid: 表guid
        :return:
        """
        r_json = self._get_bigmeta_requests(self.COLUMN_OVERVIEW, f'?columnGuid={guid}&type=COLUMN')
        if r_json:
            output = r_json.get('data', {})
            return output
        else:
            return {}

    def do(self):
        def get_columns(_offset, _limit):
            return self.db.execute_script_postgres(script='''
            select guid from bigmeta_entity_column
            where is_deleted = 0
            offset %s
            limit %s
            ''', values=[_offset, _limit])

        def insert_col_relation(_data, _market_name):
            # self.db.execute_script_postgres_no_fetch('''
            # insert into table_%s values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            # ''', _market_name)
            print(_data, _market_name)
        gmt = time.time()
        # self.truncate_col_relatin()
        # 清空表
        relation_type_code = ['ColumnDirectColumn']
        index = 0
        limit = 10000
        column_guid_list = [('database.doris_dw.ads_coupon.ads_coupon.t_coupon_bf_omm_receive_h.load_dt',)]
        while column_guid_list:
            offset = index * limit
            logging.error('start')
            # column_guid_list = get_columns(offset, limit)
            # 查询列guid
            logging.error('end')
            index += 1
            for column_guid_result in column_guid_list:
                try:
                    # column_guid = column_guid_result.guid
                    column_guid = column_guid_result[0]
                    column_overview = self.get_col_overview(column_guid)
                    for process in [x for x in column_overview.get('processExpressionList', [])]:
                        task_guid = process.get('taskGuid', '')
                        expression = process.get('expression', '')
                        task_file = task_guid.split('.')[-1].split('_', 1)[-1] + '.sql'
                        market_name = 'ddl' if '_' not in task_guid.split('.')[-1] else task_guid.split('.')[-1].split(
                            '_')[1]
                        src_col_list = [(x.get('srcGuid', ''), x.get('dstGuid', '')) for x in
                                        self.get_task_col_relations(task_guid, column_guid) if
                                        x.get('relationTypeCode', '') in relation_type_code]
                        if not src_col_list:
                            _, src_datasource_name, src_database_name, src_schema_name, src_table_name, src_column_name = [
                                '', '', '', '', '', '']
                            _, dst_datasource_name, dst_database_name, dst_schema_name, dst_table_name, dst_column_name = column_guid.split(
                                '.')
                            dst_schema_name = f"chn_{dst_schema_name.split('_')[2]}data" if dst_schema_name.startswith(
                                'gauss') else dst_schema_name
                            data = [
                                task_file, src_datasource_name, src_database_name, src_schema_name, src_table_name,
                                src_column_name,
                                dst_datasource_name, dst_database_name, dst_schema_name, dst_table_name, dst_column_name
                            ]
                            insert_col_relation(data, market_name)
                        for src_col, dst_col in src_col_list:
                            _, src_datasource_name, src_database_name, src_schema_name, src_table_name, src_column_name = src_col.split(
                                '.')
                            _, dst_datasource_name, dst_database_name, dst_schema_name, dst_table_name, dst_column_name = dst_col.split(
                                '.')
                            dst_schema_name = f"chn_{dst_schema_name.split('_')[2]}data" if dst_schema_name.startswith(
                                'gauss') else dst_schema_name
                            src_schema_name = f"chn_{src_schema_name.split('_')[2]}data" if src_schema_name.startswith(
                                'gauss') else src_schema_name
                            data = [
                                task_file, src_datasource_name, src_database_name, src_schema_name, src_table_name,
                                src_column_name,
                                dst_datasource_name, dst_database_name, dst_schema_name, dst_table_name, dst_column_name
                            ]
                            insert_col_relation(data, market_name)
                except Exception as e:
                    logging.error(e)
            # 测试退出
            break

    # def do(self):
        # with ProcessPoolExecutor() as process_pool:
        #     results = process_pool.map(func, task_list)
        #     for r in results:
        #         print(r)
        #         print(time.time() - gmt)


if __name__ == '__main__':
    ia = ImpactAnalysis()
    ia.do()
