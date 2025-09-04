import os
from collections import namedtuple
from typing import Generator

COL_INFO = ['ds', 'db', 'schema', 'tab', 'col']
TAB_INFO = ['ds', 'db', 'schema', 'tab']
SIMPLE_COL_INFO = ['src_column_guid', 'mid_process', 'dst_column_guid']
LINE_COL_INFO = ['lv', 'init_task_name', *COL_INFO, 'type',
                 *[f'src_{x}' for x in COL_INFO], *[f'dst_{x}' for x in COL_INFO]]
LINE_TAB_INFO = ['lv', 'init_task_name', *TAB_INFO, 'type',
                 *[f'src_{x}' for x in TAB_INFO], *[f'dst_{x}' for x in TAB_INFO]]
LINE_COL_NAME = ['层级', '探查任务名称', '探查列数据源名称', '探查列数据库名称', '探查列schema名称', '探查列表名称',
                 '探查列名称',
                 '血缘类型', '上游列数据源名称', '上游列数据库名称', '上游列schema名称', '上游列表名称',
                 '上游列名称',
                 '下游列数据源名称', '下游列数据库名称', '下游列schema名称', '下游列表名称', '下游列名称']
LINE_TAB_NAME = ['层级', '探查表名称', '探查列数据源名称', '探查列数据库名称', '探查列schema名称', '探查列表名称',
                 '血缘类型', '上游列数据源名称', '上游列数据库名称', '上游列schema名称', '上游列表名称',
                 '下游列数据源名称', '下游列数据库名称', '下游列schema名称', '下游列表名称']
COL_TUPLE = namedtuple('tar_node', COL_INFO)
TAB_TUPLE = namedtuple('tar_node', TAB_INFO)
LINE_COL_TUPLE = namedtuple('column', LINE_COL_INFO)
LINE_TAB_TUPLE = namedtuple('table', LINE_TAB_INFO)


class RelationNode:
    """
    列血缘结构
    """
    COL_INFO = ['ds', 'db', 'schema', 'tab', 'col']
    TAB_INFO = ['ds', 'db', 'schema', 'tab']
    LINE_COL_INFO = ['lv', 'init_task_name', *COL_INFO, 'type',
                     *[f'src_{x}' for x in COL_INFO], *[f'dst_{x}' for x in COL_INFO]]
    LINE_TAB_INFO = ['lv', 'init_task_name', *TAB_INFO, 'type',
                     *[f'src_{x}' for x in TAB_INFO], *[f'dst_{x}' for x in TAB_INFO]]
    LINE_COL_NAME = ['层级', '探查任务名称', '探查列数据源名称', '探查列数据库名称', '探查列schema名称', '探查列表名称',
                     '探查列名称',
                     '血缘类型', '上游列数据源名称', '上游列数据库名称', '上游列schema名称', '上游列表名称',
                     '上游列名称',
                     '下游列数据源名称', '下游列数据库名称', '下游列schema名称', '下游列表名称', '下游列名称']
    LINE_TAB_NAME = ['层级', '探查表名称', '探查列数据源名称', '探查列数据库名称', '探查列schema名称', '探查列表名称',
                     '血缘类型', '上游列数据源名称', '上游列数据库名称', '上游列schema名称', '上游列表名称',
                     '下游列数据源名称', '下游列数据库名称', '下游列schema名称', '下游列表名称']
    COL_TUPLE = namedtuple('tar_node', COL_INFO)
    TAB_TUPLE = namedtuple('tar_node', TAB_INFO)
    LINE_COL_TUPLE = namedtuple('column', LINE_COL_INFO)
    LINE_TAB_TUPLE = namedtuple('table', LINE_TAB_INFO)

    def __init__(self, file_name=None):
        self.traversed_set = set()
        self.column_relations = []

        self.output_file = open(os.path.join('data', file_name), 'wt', encoding='utf-8')
        self.output_file.write(','.join(self.LINE_COL_NAME) + '\n')

    def __del__(self):
        self.output_file.close()

    @staticmethod
    def make_line_col_tuple():
        return namedtuple('Column', LINE_COL_INFO)

    @staticmethod
    def make_simple_line_col_tuple():
        return namedtuple('SimpleColumn', SIMPLE_COL_INFO)

    def set_col_relations(self, col_data: tuple, lineage_datas: Generator, line_type: namedtuple):
        """
        写入，并记录已有内容
        :param line_type:
        :param col_data: 已有内容
        :param lineage_datas: 文件内容
        :return:
        """
        self.traversed_set.add(col_data)
        for line_data in lineage_datas:
            self.column_relations.append(line_type(*line_data))

    def check_traversed(self, check_data: tuple):
        """
        判读是否已有该数据
        :param check_data: 判断数据
        :return: True已有：False未有
        """
        if check_data in self.traversed_set:
            return True
        else:
            return False

    def check_rule1(self):
        if 'hive' in [x.src_ds for x in self.column_relations]:
            return True
        else:
            return False

    def flush_data(self):
        """
        写入文件，清理缓存
        :return: 1
        """
        self.output_file.writelines(','.join(str(y) for y in x) + '\n' for x in self.column_relations)
        self.clear()
        return 1

    def clear(self):
        """
        清理缓存
        :return: 1
        """
        self.column_relations.clear()
        return 1