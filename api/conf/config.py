# config.py
DB_TYPE = 'POSTGRESQL'

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
    'MAX_CONN': 10,
    'CHARSET': 'utf8mb4',
    'COLLATION': 'utf8mb4_unicode_ci'
}

MYSQL_CONFIG = {
    'host': '10.126.158.203',
    'port': 5432,
    'dbname': 'bigcustom',
    'user': 'aloudata',
    'password': '1qaz!QAZ',
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
