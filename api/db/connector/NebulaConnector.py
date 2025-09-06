import json
import logging

from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config
from api.conf.config import NEBULA_CONFIG
from api.log import timeit


class NebulaConnector:
    def __init__(self):
        self.nebula_pool = None
        assert self._init_nebula_pool()

    def _init_nebula_pool(self):
        """
        初始化nebula链接池，由于ping的timeout固定为1s，所以进行多次尝试
        :return:
        """
        config = Config()
        config.max_connection_pool_size = NEBULA_CONFIG['pool_size']
        config.timeout = NEBULA_CONFIG['timeout']
        pool = ConnectionPool()
        try_cnt = NEBULA_CONFIG['try_cnt']
        while try_cnt > 0:
            try:
                pool.init(NEBULA_CONFIG['hosts'], config)
                self.nebula_pool = pool
                return 1
            except RuntimeError as re:
                logging.error(re)
                try_cnt += -1
        return 0

    def _get_session(self):
        return self.nebula_pool.session_context(
            NEBULA_CONFIG['user'], NEBULA_CONFIG['password']
        )

    @timeit('NebulaConnector.execute_params')
    def execute_params(self, script, params):
        with self._get_session() as session:
            session.execute(f'USE {NEBULA_CONFIG["space"]};')
            r = session.execute_json_with_parameter(script, params=params)
            r_json = json.loads(r)
        return r_json

    @timeit('NebulaConnector.execute_params')
    def execute_go_params(self, script: str, params):
        with self._get_session() as session:
            session.execute(f'USE {NEBULA_CONFIG["space"]};')
            for key in params:
                script = script.replace(f'${key}', params.get(key).value)
            r = session.execute_json(script)
            r_json = json.loads(r)
        return r_json
