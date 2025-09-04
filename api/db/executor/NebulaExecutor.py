import datetime
from typing import Any

from api.db.connector.NebulaConnector import NebulaConnector
from nebula3.common.ttypes import Value, NList, Date, Time, DateTime


class NebulaExecutor:
    def __init__(self):
        self.db_connector = NebulaConnector()
        self.limit = 10

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
        # TODO: add support for GeoSpatial
        elif isinstance(value, list):
            byte_list = []
            for item in value:
                byte_list.append(self._cast_value(item))
            casted_value.set_lVal(NList(values=byte_list))
        elif isinstance(value, dict):
            # TODO: add support for NMap
            raise TypeError("Unsupported type: dict")
        else:
            raise TypeError(f"Unsupported type: {type(value)}")
        return casted_value

    def _limit_query_num(self, list_data):
        n = len(list_data)
        limit_list_data = []
        for i in range(0, n//self.limit + 1):
            limit_list_data.append(list_data[i * self.limit: (i+1) * self.limit])
        return limit_list_data

    def query_column_upstream_column(self, guids):
        _r = []
        from api.db.sql import NEBULA_QUERY_COLUMN_UPSTREAM_COLUMN
        limit_guids = self._limit_query_num(guids)
        for guid_list in limit_guids:
            params = {'guid_list': self._cast_value(guid_list)}
            _r.append(self.db_connector.execute_params(NEBULA_QUERY_COLUMN_UPSTREAM_COLUMN, params))
        return _r


if __name__ == '__main__':
    ne = NebulaExecutor()
    r = ne.query_column_upstream_column(
        ['database.hive.dwd_icc.dwd_icc.dwd_inr_pqt_unc_icc_user_follow_list_new.category_name_2']
    )
    print(r)
