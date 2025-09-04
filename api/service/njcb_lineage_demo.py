from api.log import logger
from api.utils.sql_utils import SQLUtils
from api.utils.graph_utils import GraphUtils


if __name__ == '__main__':
    logger.info('gu init')
    gu = GraphUtils()
    logger.info('gu init end; su init')
    su = SQLUtils()
    logger.info('su init end;')
    columns_list = su.get_columns(100, 0, 10000)
    for column_list in columns_list:
        logger.info('get lineage start;')
        r = gu.get_lineage(
            'COLUMN', [x.guid for x in column_list], 'INPUT'
        )
        logger.info('get lineage end;')
    logger.info('get_upstream_lineage end; batch_put_check start')
    su.batch_put_check(su.put_column_lineage, list([x, ','.join(y)] for x, y in r.items()), always=1)
    logger.info('batch_put_check end;')

