import json
import logging
import os.path
import time
from collections import namedtuple

import requests

from api.node.node_relations import RelationNode
from api.db.connector import DBConnector


class ImpactAnalysis:
    """
    影响分析
    """
    USERNAME = 'admin'
    PASSWORD = '9d86d8f1'

    # DOMAIN = 'http://bigmeta.dataapi.mcdonalds.cn/'
    DOMAIN = 'http://bigmeta-dev.mcdonalds.cn:8080/'
    API_ID = 'APP_1'
    # API_Token = '9df95b42-2130-473f-a912-e0a71fe6d98e'
    API_Token = '26cdf7ff-bafe-4b38-9c6e-ac5d3c127912'
    LOGIN = 'login'
    TASK_DETAILS = 'open/api/v1/task/details'
    TAB_DETAILS = 'open/api/v1/table/details'
    TAB_BATCH_DETAILS = 'open/api/v1/table/batchDetails'
    CUSTOM_DETAILS = 'open/api/v1/custom/details'
    COL_BATCH_DETAILS = 'open/api/v1/column/batchDetails'
    TASK_OVERVIEW = 'asset/task/overview'
    TAB_OVERVIEW = 'asset/table/overview'
    COL_RELATIONS = 'open/api/v1/column/relations'
    TAB_RELATIONS = 'open/api/v1/table/relations'
    CUSTOM_RELATIONS = 'open/api/v1/custom/relations'
    SCRIPT_EXTRACT = 'open/api/v1/reltable/scriptExtract'
    SQL_TASKS = 'open/api/v1/sql/detailsByTask'
    # 在线模拟
    LINEAGE_SIMULATION_CREATE = 'simulation/task/create'
    LINEAGE_SIMULATION_RELATION = 'simulation/task/relation'
    LINEAGE_SIMULATION_COLUMNS = 'simulation/task/columns'
    LINEAGE_SIMULATION_ERROR_INFO = 'simulation/task/errorInfo'
    # 血缘接口
    COLUMN_OVERVIEW = 'column/process/overview'
    V2 = 'lineage/custom/v2'
    TASK_DAGS = '/lineage/task/dags'

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
        self.db = DBConnector

    def _init_cookie(self, username, password):
        data = {'username': username, 'password': password}
        r = requests.request('POST', self.DOMAIN + self.LOGIN, headers=self.headers, data=json.dumps(data))
        cookie = r.headers.get('Set-Cookie')
        self.headers['Cookie'] = cookie

    def _get_bigmeta_requests(self, url, param=None, params=None, method='GET', stream=False) -> dict:
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
                                          data=json.dumps(param), stream=stream).json()
            elif params:
                r_json = requests.get(self.DOMAIN + url, params=params, headers=self.headers, stream=stream).json()
            elif param:
                r_json = requests.get(self.DOMAIN + url + param, headers=self.headers, stream=stream).json()
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

    def get_task_sqls(self, guid: str):
        r_json = self._get_bigmeta_requests(self.SQL_TASKS, f'?guid={guid}')
        if r_json:
            output_tables = r_json.get('data', {})
            return output_tables
        else:
            return {}

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

    def get_tables_info(self, guids: dict):
        """
        获取表的列
        :param guids: 表guid
        :return: 列列表
        """
        r_json = self._get_bigmeta_requests(self.TAB_BATCH_DETAILS, method='POST', param=guids, stream=True)
        return r_json

    def get_cols_info(self, guids):
        r_json = self._get_bigmeta_requests(self.COL_BATCH_DETAILS, method='POST', param=guids)
        return r_json

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

    def get_task_nodes(self, data):
        return self._get_bigmeta_requests(self.TASK_DAGS, method='POST', param=data)

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

    def column_direct_indirect_impact(self, guid: str):
        """
        获取任务输出表所有列的上游血缘
        :param guid: 任务guid
        :return:
        """

        def _dfs(index, t_c, o_t_c):
            index += 1
            traversed_node = RelationNode.COL_TUPLE(*t_c.split('.')[1:])
            if table_data.check_traversed(traversed_node):
                pass
            else:
                col_relations = self.get_col_relations(t_c)
                table_data.set_col_relations(
                    traversed_node,
                    ((index, guid, *o_t_c.split('.')[1:],
                      x.get('relationTypeCode'), *x.get('srcGuid', '.').split('.')[1:],
                      *t_c.split('.')[1:])
                     for x in col_relations if x.get('relationTypeCode')
                     in ['ColumnDirectColumn', 'ColumnIndirectTable']))
                for src_guid in (x.get('srcGuid', '') for x in col_relations
                                 if x.get('relationTypeCode') in ['ColumnDirectColumn', 'ColumnIndirectTable']):
                    _dfs(index, src_guid, o_t_c)

        guid = guid.lower()
        output_tables = self.get_output_tables(guid)
        table_data = RelationNode(guid.split('.')[-1] + '.csv')
        for output_table in output_tables:
            table_columns = self.get_tables_columns(output_table)
            for table_column in table_columns:
                _dfs(0, table_column, table_column)
            table_data.flush_data()
        return guid

    def node_direct_impact(self, node: tuple, direction='INPUT'):
        """
        获取表所有的直接上游血缘
        :param direction: INPUT-溯源/OUTPUT-扩散
        :param node: 任务guid
        :return:
        """

        def _dfs(index, n, o_t_c):
            index += 1
            e_t, t_c, _id = n
            if e_t == 'CUSTOM':
                format_id = f'..{_id}'
            elif e_t == 'TABLE':
                format_id = _id
            else:
                raise Exception('ERROR: type not in ("CUSTOM", "TABLE")')
            traversed_node = RelationNode.TAB_TUPLE(*format_id.split('.')[1:])
            if table_data.check_traversed(traversed_node):
                pass
            else:
                tab_relations = self.get_node_relations(e_t, _id, direction)
                table_data.set_col_relations(
                    traversed_node,
                    (
                        (
                            index, guid, *o_t_c.split('.')[1:], 'Direct',
                            *x.split('.')[1:], *format_id.split('.')[1:]
                        )
                        for x in (f'..{y.guid}' if y.entityType == 'CUSTOM' else y.guid for y in tab_relations
                                  if y.entityType in ['TABLE', 'CUSTOM'])
                    ), RelationNode.LINE_TAB_TUPLE
                )
                for x in (y for y in tab_relations if y.entityType in ['TABLE', 'CUSTOM']):
                    _dfs(index, x, o_t_c)

        try:
            entity_type, type_code, guid = node
            table_data = RelationNode(guid.split('.')[-1] + '.csv')
            _dfs(0, node, f'..{guid}')
            if table_data.check_rule1():
                table_data.clear()
            else:
                table_data.flush_data()
            return guid
        except:
            return ''

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

    def get_task_table(self, script_content: str) -> tuple:
        """
        OPEN API 获取任务输入输出表
        NO OPEN API 血缘模拟更方便，可以输出列
        :return:
        """
        input_table_names = set()
        output_table_names = set()
        params = {
            'dialect': 'SPARKSQL',
            'script': script_content
        }
        r = self._get_bigmeta_requests(self.SCRIPT_EXTRACT, params=params)
        sql_list = r.get('data', {}).get('sqlRelTableExtractVOList', [])
        for sql in sql_list:
            input_table_list = sql.get('inputTableNames', [])
            for input_table in input_table_list:
                input_table_names.add('.'.join(input_table.get('fullTableName', [])))
            output_table_list = sql.get('outputTableNames', [])
            for output_table in output_table_list:
                output_table_names.add('.'.join(output_table.get('fullTableName', [])))
        return input_table_names, output_table_names

    def lineage_simulation(self, script_content: str, dialect: str, ds='', db='', sch='',
                           relation_type_codes=None, variables=None) -> set:
        """
        血缘仿真，输出直接列血缘
        :param script_content: 脚本内容
        :param dialect: 语法类型
        :param relation_type_codes: 直接血缘或间接血缘
        :return:
        """
        if variables is None:
            variables = []
        if relation_type_codes is None:
            relation_type_codes = ['ColumnDirectColumn', 'ColumnIndirectTable']
        output_result = set()
        data = {
            "sqlDialect": dialect,
            "datasource": ds,
            "database": db,
            "schema": sch,
            "runVariables": True,
            "rawScriptStr": script_content,
            "variables": variables
        }
        task_info = self._get_bigmeta_requests(self.LINEAGE_SIMULATION_CREATE, param=data, method='POST')
        task_id = task_info['data']['id']
        data_e = f'?id={task_id}'
        simulation_error = self._get_bigmeta_requests(self.LINEAGE_SIMULATION_ERROR_INFO, param=data_e)
        for error_info in simulation_error['data']['errorDataList']:
            logging.error(f'Simulation ERROR: {error_info}')
        data_1 = {
            "id": task_id,
            "direction": "INPUT",
            "entityType": "Table",
            "needIndirect": True
        }
        table_relation = self._get_bigmeta_requests(self.LINEAGE_SIMULATION_RELATION, param=data_1, method='POST')
        table_id_list = [x['guid'] for x in table_relation['data']['entities']]
        for table_id in table_id_list:
            data_t = f'?guid={table_id}&id={task_id}'
            column_list = self._get_bigmeta_requests(self.LINEAGE_SIMULATION_COLUMNS, param=data_t)
            column_id_list = [x['guid'] for x in column_list['data']['columns']]
            for column_id in column_id_list:
                data_c = {
                    "id": task_id,
                    "guids": column_id,
                    "direction": "INPUT",
                    "entityType": "Column",
                    "needIndirect": True
                }
                column_relation = self._get_bigmeta_requests(self.LINEAGE_SIMULATION_RELATION, param=data_c,
                                                             method='POST')
                column_relation_list = [(x['dstGuid'], x['srcGuid'], x['relationTypeCode'])
                                        for x in column_relation['data']['relations']
                                        if x['relationTypeCode'] in relation_type_codes]
                for i in column_relation_list:
                    output_result.add(i)
        return output_result


def do():
    ia = ImpactAnalysis()
    dbc = DBConnector()
    dml_path = '../../data'
    index = 0
    variables = [{"name": "k1", "value": "v1"}]
    for a, b, c in os.walk(dml_path):
        n = len(c)
        print(c)
        for file_name in c:
            if not file_name.endswith('.sql'):
                continue
            try:
                with open(os.path.join(a, file_name), 'rt', encoding='utf8', errors='ignore') as f:
                    content = f.read()
                    database_name = a.split('/')[-1]
                    print(database_name)
                    result = ia.lineage_simulation(script_content=content, dialect='HIVE', ds='hive', db=database_name,
                                                   sch='t\_!@$^*p', variables=variables)
                    input_values = []
                    for r in result:
                        try:
                            input_info = r[0].split('.') if r[0] else ['', '', '', '', '', '']
                            output_info = r[1].split('.') if r[1] else ['', '', '', '', '', '']
                            input_column_name = '' if len(input_info) != 6 else input_info[5]
                            output_column_name = '' if len(output_info) != 6 else output_info[5]
                            data = (
                                file_name, input_info[2], input_info[4], input_column_name, output_info[2],
                                output_info[4],
                                output_column_name, r[2], a, time.strftime("%Y-%m-%d %H:%M:%S"))
                            input_values.append(data)
                        except Exception as R:
                            print(R)
                            print(r)
                    dbc.execute_batch_script_postgres_no_fetch('''
                        insert into tem_0608
                            (
                             file_name ,
                             output_db ,
                             output_table ,
                             output_column ,
                             input_db ,
                             input_table ,
                             input_column ,
                             d_type ,
                             folder_dir ,
                             gmt_create
                            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''', input_values)
            except:
                pass


if __name__ == '__main__':
    ia = ImpactAnalysis()
    # ia.get_tables_columns('database.hive.dwd_icc.dwd_icc.dwd_inr_pqt_unc_icc_user_follow_list_new')
    print(time.strftime('%H"%m"%S'))
    # a = ia.get_task_sqls('task.hive.15399_1_todoris')
    # b = ia.get_task_nodes({"depth": 1, "taskGuid": "task.hive.`214_waitfor_dwd_couponcenter.dwd_inr_pqt_unc_couponcenter_coupon_trade_interests_card全量表`", "direction": "BOTH",
    #                        "relations": ["TableDirectTable"], "entityType": "Table"})
    content = 'insert into tgab_1 select * from tasdf2 as a where a.id > 999;'
    database_name = ''
    variables = ''
    c = ia.lineage_simulation(script_content=content, dialect='HIVE', ds='hive', db=database_name,
                          sch='t\_!@$^*p', variables=variables)
    print(time.strftime('%H:%m:%S'))
    # b = ia.get_cols_info({'guids': ['database.hive.dwd_order.dwd_order.t_order_dtl_d.non_product_gross_amount']})
    print(c)

