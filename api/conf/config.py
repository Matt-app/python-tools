# config.py
DB_TYPE = 'MYSQL'

NEBULA_CONFIG = {
    'hosts': [('10.126.158.204', 9669), ('10.126.158.205', 9669), ('10.126.158.206', 9669)],
    'user': 'root',
    'password': 'nebula',
    'space': 'bigmeta',
    'pool_size': 6,
    'timeout': 50000,
    'try_cnt': 100
}

PG_CONFIG = {
    'PASSWORD': '1qaz!QAZ',
    'HOST': '10.126.158.203',
    'USER': 'aloudata',
    'DATABASE': 'bigmeta',
    'PORT': '5432',
    'MIN_CONN': 1,
    'MAX_CONN': 10
}

# 标准化 MySQL 配置，修复端口、键名
MYSQL_CONFIG = {
    'HOST': 'localhost',
    'PORT': 3306,
    'DATABASE': 'mlas',
    'USER': 'root',
    'PASSWORD': '123456',
    'MIN_CONN': 1,
    'MAX_CONN': 10,
    'CHARSET': 'utf8mb4',
    'COLLATION': 'utf8mb4_unicode_ci'
}

MAPPING = {
    'tags': {
        'table': 'output_tables',
    },
    'edges': {
        'purchased': 'purchases'  # Nebula的purchased边 -> PG的purchases表
    }
}
