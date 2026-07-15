import sqlite3

conn = sqlite3.connect('D:/pythonproject/CMO_Lua_generate/CMOLua-main/mcp/db/DB3K_504.db3')
cursor = conn.cursor()

# 验证 7V3.lua 中使用的 DBID
dbids_to_check = [
    ('DataShip', 3883, '055南昌舰'),
    ('DataShip', 2296, '052D-1昆明舰'),
    ('DataShip', 3586, '052D-2南京舰'),
    ('DataShip', 2007, '辽宁舰'),
    ('DataAircraft', 2496, 'J-15'),
    ('DataWeapon', 2868, '武器2868'),
    ('DataWeapon', 2137, '武器2137'),
    ('DataLoadout', 9682, '挂载方案9682'),
]

print('=== DBID 验证结果 ===')
for table, dbid, desc in dbids_to_check:
    cursor.execute(f'SELECT Name FROM "{table}" WHERE ID = ?', (dbid,))
    result = cursor.fetchone()
    if result:
        print(f'[OK] {table}.ID={dbid} -> {result[0]} ({desc})')
    else:
        print(f'[MISS] {table}.ID={dbid} -> 未找到 ({desc})')

conn.close()
