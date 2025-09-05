from typing import Any

from api.db.connector.NebulaConnector import NebulaConnector
from nebula3.common.ttypes import Value, NList, Date, Time, DateTime
from api.log import logger, timeit
import datetime


class NebulaExecutor:
    def __init__(self):
        self.db_connector = NebulaConnector()
        # 每次入参 guid 的最大数量
        self.limit = 10
        # 每次查询返回最多的结果数量（按行截断）
        self.result_limit = 1000

    def _cast_value(self, value: Any) -> Value:
        """
        Cast the value to nebula Value type
        ref: https://github.com/vesoft-inc/nebula/blob/master/src/common/datatypes/Value.cpp
        :param value: the value to be casted
        :return: the casted value
        """
        casted_value = Value()
        if isinstance(value, bool):
            casted_value.set_bVal(value)
        elif isinstance(value, int):
            casted_value.set_iVal(value)
        elif isinstance(value, str):
            casted_value.set_sVal(value)
        elif isinstance(value, float):
            casted_value.set_fVal(value)
        elif isinstance(value, (list, tuple)):
            # 递归转换列表元素
            l = NList()
            l.values = [self._cast_value(v) for v in value]
            casted_value.set_lVal(l)
        elif isinstance(value, datetime.date):
            date_value = Date(year=value.year, month=value.month, day=value.day)
            casted_value.set_dVal(date_value)
        elif isinstance(value, datetime.time):
            time_value = Time(
                hour=value.hour,
                minute=value.minute,
                sec=value.second,
                microsec=value.microsecond,
            )
            casted_value.set_tVal(time_value)
        elif isinstance(value, datetime.datetime):
            datetime_value = DateTime(
                year=value.year,
                month=value.month,
                day=value.day,
                hour=value.hour,
                minute=value.minute,
                sec=value.second,
                microsec=value.microsecond,
            )
            casted_value.set_dtVal(datetime_value)
        return casted_value

    def _limit_query_num(self, list_data):
        n = len(list_data)
        limit_list_data = []
        # 修正切片逻辑，避免末尾空切片
        for i in range(0, (n + self.limit - 1) // self.limit):
            limit_list_data.append(list_data[i * self.limit: (i + 1) * self.limit])
        return limit_list_data

    def _limit_query_result(self, result_json: dict) -> dict:
        """限制每次查询的返回行数，截断到 self.result_limit。"""
        if not isinstance(result_json, dict):
            return result_json
        key = 'result' if 'result' in result_json else ('results' if 'results' in result_json else None)
        if not key:
            return result_json
        lst = result_json.get(key, []) or []
        for item in lst:
            data = item.get('data')
            if isinstance(data, list) and len(data) > self.result_limit:
                item['data'] = data[: self.result_limit]
        return result_json

    @timeit('NebulaExecutor.query_column_upstream_column')
    def query_column_upstream_column(self, guids):
        _r = []
        from api.db.sql import NEBULA_QUERY_COLUMN_UPSTREAM_COLUMN
        limit_guids = self._limit_query_num(guids)
        for guid_list in limit_guids:
            params = {'guid_list': self._cast_value(guid_list)}
            resp = self.db_connector.execute_params(NEBULA_QUERY_COLUMN_UPSTREAM_COLUMN, params)
            _r.append(self._limit_query_result(resp))
        logger.info('nebula query batches=%d, total_input=%d, per_batch_limit=%d, result_limit=%d',
                    len(limit_guids), len(guids), self.limit, self.result_limit)
        return _r


class NebulaExecutorTest:
    """简单测试类，用于本地验证 NebulaExecutor 主功能。"""
    def __init__(self):
        self.executor = NebulaExecutor()

    def test_query_column_upstream_column(self):
        sample = ['database.hive.dwd_icc.dwd_icc.dwd_inr_pqt_unc_icc_user_follow_list_new.category_name_2']
        r = self.executor.query_column_upstream_column(sample)
        print(r)
        return r


if __name__ == '__main__':
    NebulaExecutorTest().test_query_column_upstream_column()
