import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import islice
from multiprocessing import cpu_count

from api.log import logger
from api.utils.sql_utils import SQLUtils
from api.utils.graph_utils import GraphUtils


def chunks(iterable, size):
    it = iter(iterable)
    while True:
        batch = list(islice(it, size))
        if not batch:
            break
        yield batch


def process_batch(batch_guids):
    gu = GraphUtils()
    r = gu.get_lineage('COLUMN', batch_guids, 'INPUT')
    # 返回 (upstream_columns, dst_column_guid) 顺序，满足 INSERT SQL
    return [(','.join(sorted(srcs)), dst) for dst, srcs in r.items()]


def do():
    logger.info('init SQLUtils')
    su = SQLUtils()
    logger.info('load column guid generator')
    columns_list = su.get_columns(1, 0, 10)

    use_multiproc = os.getenv('MULTIPROC', '0') == '1'
    if use_multiproc:
        workers = max(1, min(cpu_count(), 4))
        logger.info('Enable multiprocessing: workers=%d', workers)
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = []
            in_flight = 0
            max_in_flight = workers * 2
            for column_list in columns_list:
                batch_guids = [x.guid for x in column_list]
                futures.append(executor.submit(process_batch, batch_guids))
                in_flight += 1
                if in_flight >= max_in_flight:
                    for fut in as_completed(futures):
                        payload = fut.result()
                        if payload:
                            su.batch_put_check(su.put_column_lineage, payload, always=1)
                        in_flight -= 1
                    futures.clear()
            # 收尾
            for fut in as_completed(futures):
                payload = fut.result()
                if payload:
                    su.batch_put_check(su.put_column_lineage, payload, always=1)
    else:
        # 单进程：逐批处理并立即落库
        for column_list in columns_list:
            batch_guids = [x.column_guid for x in column_list]
            logger.info('get lineage start; batch size=%d', len(batch_guids))
            gu = GraphUtils()
            r = gu.get_lineage('COLUMN', batch_guids, 'INPUT')
            payload = [(','.join(sorted(srcs)), dst) for dst, srcs in r.items()]
            batch_size = len(payload)
            su.batch_put_check(su.put_column_lineage, payload, always=1)
            logger.info('batch done, inserted=%d', batch_size)

    logger.info('all done')


if __name__ == '__main__':
    # gu = GraphUtils()
    # r = gu.get_lineage('COLUMN', ['database.hive.dws_people.dws_people.t_payroll_employee_statistic_m.edu_level'], 'INPUT')
    # print(r)
    do()
