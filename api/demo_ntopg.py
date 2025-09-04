import json
import logging
import traceback

from conf.config import NEBULA_CONFIG, PG_CONFIG, MAPPING
from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config
import psycopg2
from psycopg2 import sql, extras


class NebulaToPG:
    def __init__(self):
        self.nebula_pool = self.init_nebula_pool()
        self.pg_conn = self.init_pg_connection()

    def init_nebula_pool(self):
        config = Config()
        config.default_space = NEBULA_CONFIG["space"]
        pool = ConnectionPool()
        pool.init(NEBULA_CONFIG["hosts"], config)
        return pool

    def init_pg_connection(self):
        return psycopg2.connect(**PG_CONFIG)

    def export_tags_to_pg(self, tag_name, pg_table):
        """导出指定标签到PostgreSQL表"""
        with self.nebula_pool.session_context(
                NEBULA_CONFIG["user"], NEBULA_CONFIG["password"]
        ) as session:
            session.execute(f"USE bigmeta;")
            # 获取标签属性结构
            result = session.execute(f"DESCRIBE TAG {tag_name}")
            if not result.is_succeeded():
                logging.error(result.error_msg())
                raise Exception(f"获取标签结构失败: {result.error_msg()}")

            properties = []
            for row in result:
                properties.append(row.values()[0].as_string())  # 属性名

            # 创建PG表
            with self.pg_conn.cursor() as pg_cursor:
                columns = ["vid TEXT PRIMARY KEY"] + [f"{prop} TEXT" for prop in properties]
                create_table = sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {} ({})"
                ).format(sql.Identifier(pg_table), sql.SQL(', ').join(map(sql.SQL, columns)))

                pg_cursor.execute(create_table)

            # 导出数据
            last_id = ""  # 初始为空
            batch_size = 1000
            while True:
                query = f"""
                                MATCH (v:{tag_name})
                                {'WHERE id(v) > "' + last_id + '"' if last_id else ''}
                                WITH id(v) as id_v, v
                                ORDER BY id_v
                                RETURN v
                                LIMIT {batch_size}
                                """
                result = session.execute_json(query)
                result_json = json.loads(result)
                if not result_json.get('results', [{}])[0].get('data', []):
                    logging.error(result_json)
                    break
                with self.pg_conn.cursor() as pg_cursor:
                    # 构建 SQL 模板
                    conflict_key = 'vid'
                    columns = [conflict_key] + properties
                    insert_sql = sql.SQL("""
                                                           INSERT INTO {table} ({fields})
                                                           VALUES %s
                                                           ON CONFLICT ({conflict_key}) DO UPDATE SET {updates}
                                                       """).format(
                        table=sql.Identifier(pg_table),
                        fields=sql.SQL(', ').join(map(sql.Identifier, columns)),
                        conflict_key=sql.Identifier(conflict_key),
                        updates=sql.SQL(', ').join([
                            sql.SQL("{col} = EXCLUDED.{col}").format(col=sql.Identifier(col))
                            for col in properties
                        ])
                    )
                    data_list = []
                    for results in result_json.get('results'):
                        for row in results.get('data'):
                            meta = row.get('meta', [])
                            meta_row = row.get('row', [])
                            n = min(len(meta), len(meta_row))
                            for i in range(n):
                                vid = meta[i].get('id', '')
                                props = meta_row[i]
                                values = [vid] + [props.get(f'{tag_name}.{prop}', "") for prop in properties]
                                data_list.append(values.copy())
                                if len(data_list) > batch_size:
                                    extras.execute_values(pg_cursor, insert_sql, data_list)
                                    self.pg_conn.commit()
                                    logging.error(f"标签 {tag_name} 导出{len(data_list)} -> PG表 {pg_table}")
                                    data_list.clear()

                                last_id = vid  # 更新 last_id
                    extras.execute_values(pg_cursor, insert_sql, data_list)
                    self.pg_conn.commit()
                    logging.error(f"标签 {tag_name} 导出{len(data_list)} -> PG表 {pg_table}")

    # def export_edges_to_pg(self, edge_name, pg_table):
    #     """导出指定边到PostgreSQL表"""
    #     with self.nebula_pool.session_context(
    #             NEBULA_CONFIG["user"], NEBULA_CONFIG["password"]
    #     ) as session:
    #         # 获取边属性结构
    #         result = session.execute(f"DESCRIBE EDGE {edge_name}")
    #         if not result.is_succeeded():
    #             raise Exception(f"获取边结构失败: {result.error_msg()}")
    #
    #         properties = []
    #         for row in result:
    #             properties.append(row[0])  # 属性名
    #
    #         # 创建PG表
    #         with self.pg_conn.cursor() as pg_cursor:
    #             columns = [
    #                           "src_id TEXT",
    #                           "dst_id TEXT",
    #                           "rank INT DEFAULT 0"
    #                       ] + [f"{prop} TEXT" for prop in properties]
    #
    #             create_table = sql.SQL(
    #                 "CREATE TABLE IF NOT EXISTS {} ({}, PRIMARY KEY (src_id, dst_id, rank))"
    #             ).format(sql.Identifier(pg_table), sql.SQL(', ').join(map(sql.SQL, columns)))
    #
    #             pg_cursor.execute(create_table)
    #
    #         # 导出数据
    #         offset = 0
    #         batch_size = 1000
    #         while True:
    #             query = (
    #                 f"FETCH PROP ON {edge_name} * "
    #                 f"YIELD edge AS e "
    #                 f"LIMIT {batch_size} OFFSET {offset}"
    #             )
    #             result = session.execute(query)
    #
    #             if not result.is_succeeded() or not result.row_values():
    #                 break
    #
    #             with self.pg_conn.cursor() as pg_cursor:
    #                 for row in result:
    #                     edge = row.as_map().get("e")
    #                     src = edge.get_src().as_string()
    #                     dst = edge.get_dst().as_string()
    #                     rank = edge.get_ranking()
    #                     props = edge.properties()
    #
    #                     columns = ["src_id", "dst_id", "rank"] + properties
    #                     values = [src, dst, rank] + [
    #                         props.get(prop, "").as_string() for prop in properties
    #                     ]
    #
    #                     insert = sql.SQL(
    #                         "INSERT INTO {} ({}) VALUES ({}) "
    #                         "ON CONFLICT (src_id, dst_id, rank) DO UPDATE SET {}"
    #                     ).format(
    #                         sql.Identifier(pg_table),
    #                         sql.SQL(', ').join(map(sql.Identifier, columns)),
    #                         sql.SQL(', ').join(map(sql.Literal, values)),
    #                         sql.SQL(', ').join([
    #                             sql.SQL("{} = EXCLUDED.{}").format(
    #                                 sql.Identifier(prop), sql.Identifier(prop)
    #                             for prop in properties
    #                         ])
    #                     )
    #
    #                     pg_cursor.execute(insert)
    #
    #                     offset += batch_size
    #
    #                     self.pg_conn.commit()
    #                     print(f"边 {edge_name} 导出完成 -> PG表 {pg_table}")

    def run(self):
        """执行所有转换"""
        # 导出所有标签
        with self.nebula_pool.session_context(
                NEBULA_CONFIG["user"], NEBULA_CONFIG["password"]
        ) as session:
            session.execute(f"USE bigmeta;")
            # 获取标签属性结构
            result = session.execute_json(f"SHOW TAGS")
        for nebula_tags in json.loads(result).get('results', []):
            for data in nebula_tags.get('data', []):
                nebula_tag_row = data.get('row')
                for nebula_tag in nebula_tag_row:
                    try:
                        self.export_tags_to_pg(str(nebula_tag), f'output_{nebula_tag}')
                    except:
                        traceback.print_exc()

        # 导出所有边
        # for nebula_edge, pg_table in MAPPING["edges"].items():
        #     self.export_edges_to_pg(nebula_edge, pg_table)

    def close(self):
        self.pg_conn.close()
        self.nebula_pool.close()


if __name__ == "__main__":
    converter = NebulaToPG()
    converter.run()
    converter.close()
