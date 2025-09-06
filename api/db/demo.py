from api.db import SQLExecutor
from api.db.connector.NebulaConnector import NebulaConnector

if __name__ == '__main__':
    nc = NebulaConnector()
    a = nc.execute_params('''
    MATCH ()-[p1:column_input_process]->()-[p2:process_output_column]->(c) RETURN distinct id(c) LIMIT 10000;
    ''', None)

    su = SQLExecutor('MYSQL')
    for b in a.get('results', {}):
        c = b.get('data', [])
        d = [x.get('row', '') for x in c]
        su.init_column_guid(d)
