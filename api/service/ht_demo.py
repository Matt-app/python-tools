import pymysql
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='data_migration.log'
)


class GoldenDBMigrator:
    def __init__(self):
        # 数据库连接配置
        self.db_config = {
            'host': 'your_goldendb_host',
            'port': 3306,
            'user': 'your_username',
            'password': 'your_password',
            'database': 'your_database',
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor
        }

        # 迁移参数配置
        self.migration_config = {
            'source_table': 'orders',
            'target_table': 'orders_history',
            'time_column': 'create_time',
            'retention_days': 365,  # 保留最近365天数据
            'batch_size': 1000,  # 每批迁移1000条
            'sleep_interval': 1  # 批次间隔1秒
        }

    def get_db_connection(self):
        """获取数据库连接"""
        return pymysql.connect(**self.db_config)

    def migrate_data(self):
        """执行数据迁移"""
        start_time = datetime.now()
        logging.info("=" * 50)
        logging.info(f"开始数据迁移任务 {start_time}")

        try:
            conn = self.get_db_connection()
            with conn:
                # 计算截止时间点
                cutoff_date = datetime.now() - timedelta(days=self.migration_config['retention_days'])

                # 获取待迁移数据总量
                with conn.cursor() as cursor:
                    count_sql = f"""
                        SELECT COUNT(*) AS total 
                        FROM {self.migration_config['source_table']} 
                        WHERE {self.migration_config['time_column']} < %s
                    """
                    cursor.execute(count_sql, (cutoff_date,))
                    total = cursor.fetchone()['total']

                if total == 0:
                    logging.info("没有需要迁移的数据")
                    return

                logging.info(f"待迁移数据总量: {total} 条")

                # 分批迁移
                migrated = 0
                while migrated < total:
                    with conn.cursor() as cursor:
                        # 开启事务
                        conn.begin()

                        try:
                            # 迁移数据到历史表
                            insert_sql = f"""
                                INSERT INTO {self.migration_config['target_table']} 
                                SELECT * FROM {self.migration_config['source_table']} 
                                WHERE {self.migration_config['time_column']} < %s 
                                LIMIT %s
                            """
                            cursor.execute(insert_sql, (cutoff_date, self.migration_config['batch_size']))
                            inserted_rows = cursor.rowcount

                            if inserted_rows == 0:
                                break

                            # 从原表删除已迁移的数据
                            delete_sql = f"""
                                DELETE FROM {self.migration_config['source_table']} 
                                WHERE {self.migration_config['time_column']} < %s 
                                LIMIT %s
                            """
                            cursor.execute(delete_sql, (cutoff_date, inserted_rows))
                            deleted_rows = cursor.rowcount

                            # 验证一致性
                            if inserted_rows != deleted_rows:
                                conn.rollback()
                                logging.error(f"迁移不一致: 插入{inserted_rows}条, 删除{deleted_rows}条")
                                raise Exception("迁移数据不一致")

                            conn.commit()
                            migrated += inserted_rows
                            logging.info(f"已迁移: {migrated}/{total} ({migrated / total:.1%})")

                            # 批次间隔
                            if migrated < total:
                                time.sleep(self.migration_config['sleep_interval'])

                        except Exception as e:
                            conn.rollback()
                            logging.error(f"迁移失败: {str(e)}")
                            raise

                logging.info(f"迁移完成. 总计迁移 {migrated} 条数据")

        except Exception as e:
            logging.error(f"迁移任务异常终止: {str(e)}")
        finally:
            duration = datetime.now() - start_time
            logging.info(f"迁移任务耗时: {duration}")

    def start_scheduler(self):
        """启动定时任务"""
        scheduler = BlockingScheduler()
        # 每天凌晨2点执行
        scheduler.add_job(
            self.migrate_data,
            'cron',
            hour=2,
            minute=0,
            timezone='Asia/Shanghai'
        )

        logging.info("启动定时迁移任务调度器...")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logging.info("停止定时迁移任务调度器...")
            scheduler.shutdown()


if __name__ == '__main__':
    migrator = GoldenDBMigrator()
    # 直接执行一次测试
    # migrator.migrate_data()

    # 启动定时任务
    migrator.start_scheduler()