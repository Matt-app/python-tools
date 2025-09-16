from api.db import SQLExecutor
from api.conf.config import DB_TYPE


class SQLUtils:
    # 避免多次创建连接池
    _executor = None

    def __init__(self):
        self.limit = 1000
        if SQLUtils._executor is None:
            SQLUtils._executor = SQLExecutor(DB_TYPE)

    @property
    def executor(self):
        return self._executor

    def batch_put_check(self, func, data, always=0):
        if len(data) > self.limit or always:
            if data:
                func(list(data))
            data.clear()
        else:
            pass

    def get_columns(self, limit, offset, total):
        r = self.executor.query_column_guid_list(total, limit, offset)
        yield from r

    def get_tables(self):
        r = self.executor.query_table_guid_list()
        return r

    def get_upstream_guid_list(self, guid):
        # 修复：传入单个 guid 给占位符 %s
        r = self.executor.query_upstream_column_guid_list(guid)
        return r

    def get_upstream_guid_list_batch(self, guids):
        """
        批量查询多个目标列的上游血缘
        :param guids: list[str]
        :return: list[namedtuple(dst_column_guid, upstream_columns)]
        """
        return self.executor.query_upstream_column_guid_list_batch(guids)

    def put_column_lineage(self, lineage_list):
        r = self.executor.insert_column_lineage(lineage_list)
        return r
