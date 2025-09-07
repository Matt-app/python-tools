from collections import defaultdict

from api.node.node_relations import RelationNode
from api.db.executor.NebulaExecutor import NebulaExecutor
from api.utils.sql_utils import SQLUtils
from api.log import logger, timeit


class GraphUtils:
    def __init__(self):
        self.ne = NebulaExecutor()
        self.traversed_set = set()
        self.column_lineage_tuple = RelationNode.make_simple_line_col_tuple()
        # 缓存
        self.su = SQLUtils()
        self.table_dict = None

    def init_table_list(self):
        self.table_dict = {x.table_guid: x.table_type for x in self.su.get_tables()}

    def _check_traversed_node(self, check_data: tuple):
        """
        判读是否已有该数据
        :param check_data: 判断数据
        :return: True已有：False未有
        """
        if check_data in self.traversed_set:
            return True
        else:
            self.traversed_set.add(check_data)
            return False

    def _get_traversed_nodes(self, check_data: set):
        """

        :param check_data:
        :return:
        """
        _traversed_nodes = self.traversed_set.intersection(check_data)
        self.traversed_set.update(check_data)
        return _traversed_nodes

    @timeit('GraphUtils._get_column_upstream_relation')
    def _get_column_upstream_relation(self, guid_list: list):
        """
        输出 上/下游所有资产的热度，热度为相关列、表、资产数量
        资产数量去重，多个任务相同关系计算为1个热度
        :param guid_list:
        :return: set(tuple($src_col_guid, $mid_process_guid, $dst_col_guid))
        """
        result_set = set()
        query_results_list = self.ne.query_column_upstream_column(guid_list)
        for query_results in query_results_list:
            results_key = 'result' if 'result' in query_results else ('results' if 'results' in query_results else None)
            if not results_key:
                continue
            for query_result in query_results.get(results_key, []):
                data_list = query_result.get('data', []) or []
                columns = query_result.get('columns', []) or []
                for item in data_list:
                    if isinstance(item, dict) and 'row' in item:
                        meta_list = item.get('row', []) or []
                        if len(meta_list) == 3:
                            src_col_guid = meta_list[0]
                            mid_process_guid = meta_list[1]
                            dst_col_guid = meta_list[2]
                            result_set.add(self.column_lineage_tuple(src_col_guid, mid_process_guid, dst_col_guid))
        return result_set

    @timeit('GraphUtils.get_relation')
    def get_relation(self, guid_list, node_type, direction):
        """
        todo 增加批量限制
        todo check guid 合法
        todo check guid 是否为临时表
        :param guid_list:
        :param node_type: COLUMN/
        :param direction: INPUT/OUTPUT
        :return: COLUMN-INPUT: set(tuple($src_col_guid, $mid_process_guid, $dst_col_guid))
        """
        relation_result_d = []
        if node_type == 'COLUMN':
            if direction == 'INPUT':
                relation_result = self._get_column_upstream_relation(guid_list)
                for relation in relation_result:
                    src_table_type = self.table_dict.get('.'.join(relation.src_column_guid.split('.')[:-1]))
                    if src_table_type:
                        if src_table_type in ('TABLE', 'VIEW'):
                            relation_result_d.append(relation)
                        elif src_table_type == 'TEMP_TABLE':
                            relation_result_d.extend(
                                self.get_penetration_relation(
                                    relation.dst_column_guid, relation.src_column_guid, node_type, direction
                                )
                            )
                        else:
                            raise Exception('get_relation error')
                return relation_result_d

    def get_penetration_relation(self, ana_guid, guid, node_type, direction):
        traversed_node_set = set()
        relation_result_d = []

        def _dfs():
            if guid in traversed_node_set:
                return []
            else:
                traversed_node_set.add(guid)
            if node_type == 'COLUMN':
                if direction == 'INPUT':
                    relation_result = self._get_column_upstream_relation([guid])
                    for relation in relation_result:
                        src_table_type = self.table_dict.get('.'.join(relation.src_column_guid.split('.')[:-1]))
                        if src_table_type:
                            if src_table_type == 'TABLE':
                                relation_result_d.append(relation.src_column_guid)
                            elif src_table_type == 'TEMP_TABLE':
                                relation_result_d.extend(
                                    self.get_penetration_relation(ana_guid, src_table_type, node_type, direction)
                                )
                    penetration_relation_result = [
                        self.column_lineage_tuple(x, '', ana_guid) for x in relation_result_d
                    ]
                    return penetration_relation_result
        return _dfs()

    @timeit('GraphUtils._query_upstream_guid_list')
    def _query_upstream_guid_list(self, dst_guid):
        query_result = self.su.get_upstream_guid_list(dst_guid)
        upstream = []
        try:
            # execute_script 返回的是 namedtuple 列表，字段名 upstream_columns
            if query_result and len(query_result) > 0:
                value = getattr(query_result[0], 'upstream_columns', None)
                if value:
                    # 入库格式为以逗号分隔的字符串
                    upstream = [x for x in str(value).split(',') if x]
        except Exception as e:
            logger.error('parse upstream_columns error: %s', e)
        logger.info('_query_upstream_guid_list(%s): %s', dst_guid, upstream)
        return upstream

    @timeit('GraphUtils.get_lineage')
    def get_lineage(self, node_type, node_id_list, direction):
        """

        :param node_type: 实体类型
        :param node_id_list: 实体列表
        :param direction: 探索方向
        :return:
        """
        lineage_result = defaultdict(set)
        reverse_lineage_result = defaultdict(set)

        def _dfs(index, _node_type, all_node_ids: list, _direction):
            """

            :param index: 层级
            :param _node_type: 实体类型
            :param all_node_ids: 实体列表
            :param _direction: 方向
            :return:
            """
            logger.info(f'start get {len(all_node_ids)} {_direction} lineage.')
            _guid_list = set()
            index += 1
            # 获取遍历过的节点
            traversed_node_set = self._get_traversed_nodes(set(all_node_ids))
            # 根据数据库信息更新结果列表，防止重复溯源
            for node_id in all_node_ids:
                upstream_guid_list = self._query_upstream_guid_list(node_id)
                if upstream_guid_list:
                    lineage_result[node_id].update(upstream_guid_list)
                    traversed_node_set.add(node_id)

            # 更新实体字典，删除遍历过的节点
            all_node_ids = [x for x in all_node_ids if x not in traversed_node_set]
            # 获取血缘信息
            relations = self.get_relation(all_node_ids, _node_type, _direction)
            # 更新结果列表并开启下次迭代
            for src_col_guid, _, dst_col_guid in relations:
                # 更新逆向结果集
                reverse_lineage_result[src_col_guid].add(dst_col_guid)
                reverse_lineage_result[src_col_guid].update(reverse_lineage_result.get(dst_col_guid, set()))
                # 更新结果集
                lineage_result[dst_col_guid].add(src_col_guid)
                for dcg in reverse_lineage_result.get(dst_col_guid, set()):
                    lineage_result[dcg].update(lineage_result.get(dst_col_guid, set()))
                _guid_list.add(src_col_guid)
            if _guid_list:
                _dfs(index, _node_type, list(_guid_list), _direction)
        _dfs(0, node_type,node_id_list, direction)
        return lineage_result



