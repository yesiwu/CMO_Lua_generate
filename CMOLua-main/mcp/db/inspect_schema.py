import sqlite3

conn = sqlite3.connect('D:/pythonproject/CMO_Lua_generate/CMOLua-main/mcp/db/DB3K_504.db3')
cursor = conn.cursor()

# 查看核心表的结构和样例数据
tables_to_inspect = [
    'DataShip', 'DataAircraft', 'DataWeapon', 'DataSensor', 
    'DataLoadout', 'DataMount', 'DataPropulsion', 'DataFuel'
]

for table in tables_to_inspect:
    print(f'\n=== {table} ===')
    try:
        # 获取表结构
        cursor.execute(f'PRAGMA table_info("{table}")')
        columns = cursor.fetchall()
        print('Columns:', [c[1] for c in columns])
        
        # 获取前3行数据
        cursor.execute(f'SELECT * FROM "{table}" LIMIT 3')
        rows = cursor.fetchall()
        for i, row in enumerate(rows):
            print(f'Row {i+1}:', row[:5], '...')  # 只显示前5列
    except Exception as e:
        print(f'Error: {e}')

conn.close()
