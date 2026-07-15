import sqlite3

conn = sqlite3.connect('D:/pythonproject/CMO_Lua_generate/CMOLua-main/mcp/db/DB3K_504.db3')
cursor = conn.cursor()

# 获取 DataShip 完整结构
cursor.execute('PRAGMA table_info("DataShip")')
columns = cursor.fetchall()

print('=== DataShip 表结构 ===')
for col in columns:
    cid, name, dtype, notnull, dflt, pk = col
    pk_mark = ' [PK]' if pk else ''
    null_mark = ' NOT NULL' if notnull else ''
    print(f'  {name}: {dtype}{null_mark}{pk_mark}')

print(f'\n总列数: {len(columns)}')

# 查看几行样例数据
print('\n=== 样例数据 (3行) ===')
cursor.execute('SELECT * FROM DataShip LIMIT 3')
rows = cursor.fetchall()
col_names = [c[1] for c in columns]

for i, row in enumerate(rows):
    print(f'\n--- Row {i+1} ---')
    for name, val in zip(col_names, row):
        if val is not None and val != '-' and val != 0:
            print(f'  {name}: {val}')

conn.close()
