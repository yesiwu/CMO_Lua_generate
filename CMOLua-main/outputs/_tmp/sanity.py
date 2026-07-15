import sqlite3, os
DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
print(f"file size: {os.path.getsize(DB)} bytes")

con = sqlite3.connect(DB)
cur = con.cursor()
n = cur.execute("SELECT COUNT(*) FROM DataFacility").fetchone()
print("DataFacility row count:", n)
n2 = cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()
print("sqlite_master table count:", n2)

# 看 DataFacility 表的前 3 行（用 try）
try:
    rows = list(cur.execute("SELECT * FROM DataFacility LIMIT 3"))
    print("DataFacility head 3:")
    for r in rows: print(" ", r)
except Exception as e:
    print("ERR:", e)

# COUNT * 不带 where
print("\n=== COUNT(*) FROM DataFacility (无 where) ===")
try:
    print(cur.execute("SELECT COUNT(*) FROM DataFacility").fetchone())
except Exception as e:
    print("ERR:", e)

# 单条
print("\n=== SELECT 1 行无 where ===")
try:
    row = cur.execute("SELECT ID, Name FROM DataFacility LIMIT 1").fetchone()
    print(row)
except Exception as e:
    print("ERR:", e)

con.close()
