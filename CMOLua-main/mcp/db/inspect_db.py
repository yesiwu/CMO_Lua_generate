import sqlite3

conn = sqlite3.connect('D:/pythonproject/CMO_Lua_generate/CMOLua-main/mcp/db/DB3K_504.db3')
cursor = conn.cursor()

# 获取所有表名
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
print('=== 数据库表列表 ===')
for t in tables:
    print(t[0])

# 获取每个表的行数
print('\n=== 各表行数 ===')
for t in tables:
    try:
        cursor.execute(f'SELECT COUNT(*) FROM "{t[0]}"')
        count = cursor.fetchone()[0]
        print(f'{t[0]}: {count} 行')
    except Exception as e:
        print(f'{t[0]}: 错误 - {e}')

conn.close()
