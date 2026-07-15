import sqlite3
con = sqlite3.connect(r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3")   # 换成真实路径
cur = con.cursor()
for (name,) in cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND lower(name) LIKE '%loadout%'"):
    print(name)