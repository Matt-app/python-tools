import logging

import pandas as pd
from collections import defaultdict, namedtuple
from tqdm import tqdm
from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config

from bigmeta_preprocess.api.utils.db_utils.DBConnector import DBConnector


class FormatRelation:
    def __init__(self):
        self.gp_conn = DBConnector()
        self.table_relations = set()
        column_names = [
            'src_datasource', 'src_database', 'src_schema', 'src_table', 'dst_datasource', 'dst_database', 'dst_schema',
            'dst_table']
        self.TABLE_RELATION = namedtuple('table_relation', column_names)
        self.query_table_relation_script = '''
        select table_relations 
        from bigmeta_entity_task 
        where is_deleted = 0 and table_relations is not null;
        '''
        self.insert_table_relation_script = '''
        INSERT INTO mcd_table_relations
        (src_datasource, src_database, src_schema, src_table, dst_datasource, dst_database, dst_schema, dst_table)
        VALUES(%s, %s, %s, %s, %s, %s, %s, %s);
        '''

    def get_table_relations(self):
        # 读取原始数据
        relation_data = self.gp_conn.execute_stream_script_postgres(self.query_table_relation_script)
        for i in relation_data:
            for table_relation in i.table_relations:
                for input_table in table_relation['inputTableGuids']:
                    self.table_relations.add(
                        self.TABLE_RELATION(
                            *input_table.split('.')[1:], *table_relation['outputTableGuid'].split('.')[1:]
                        )
                    )

    def process_table_relations(self):

        # 数据清洗
        df = pd.DataFrame(self.table_relations)
        df = df.drop_duplicates()  # 去重

        # 构建数据库级关系
        db_relations = defaultdict(lambda: defaultdict(int))
        for _, row in tqdm(df.iterrows(), total=len(df)):
            key = (row['source_db'], row['target_db'])
            db_relations[key]['count'] += 1

        # 构建表级关系（按需加载）
        table_edges = []
        for _, row in df.iterrows():
            source = f"{row['source_db']}.{row['source_table']}"
            target = f"{row['target_db']}.{row['target_table']}"
            table_edges.append((source, target))

        return db_relations, table_edges

    def export_to_nebula(db_relations, table_edges):
        """将关系导入图数据库"""
        # 配置连接
        config = Config()
        conn_pool = ConnectionPool()
        conn_pool.init([('127.0.0.1', 9669)], config)

        with conn_pool.session_context('root', 'nebula') as session:
            # 创建数据库级关系
            for (source_db, target_db), rel_data in db_relations.items():
                query = f"""
                    INSERT VERTEX database(name) VALUES "{source_db}":("{source_db}")
                    INSERT VERTEX database(name) VALUES "{target_db}":("{target_db}")
                    INSERT EDGE database_dependency(count) 
                        VALUES "{source_db}"->"{target_db}":({rel_data['count']})
                """
                session.execute(query)

            # 创建表级关系（批量插入）
            batch_size = 1000
            for i in tqdm(range(0, len(table_edges), batch_size)):
                batch = table_edges[i:i + batch_size]
                values = ",".join([f'"{src}"->"{dst}":()' for src, dst in batch])
                query = f"INSERT EDGE table_dependency VALUES {values}"
                session.execute(query)

    def export_to_pg(self, batch_num=1000):
        self.table_relations = list(self.table_relations)
        n = len(self.table_relations)
        logging.info('total: %s', n)
        for i in range(n//batch_num+1):
            r = self.gp_conn.execute_batch_script_postgres_no_fetch(
                self.insert_table_relation_script, self.table_relations[batch_num*i: batch_num*(1+i)])
            logging.info('num: %s', r)


if __name__ == "__main__":
    fr = FormatRelation()
    fr.get_table_relations()
    fr.export_to_pg()
    # fr.export_to_nebula(db_rels, table_edges)
