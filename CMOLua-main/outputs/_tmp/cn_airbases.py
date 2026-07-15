import sqlite3
DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== 中国 (Country=2018) 机场 (Category IN 2001/2002/2003/9001) 按跑道长度降序 ===")
rows = list(cur.execute("""
    SELECT ID, Name, Category, Length, Width
    FROM DataFacility
    WHERE OperatorCountry=2018
      AND Category IN (2001,2002,2003,9001)
      AND Deprecated='No'
    ORDER BY Length DESC
"""))
print(f"总数: {len(rows)}\n")
for r in rows:
    print(f"  DBID={r[0]:>5}  Cat={r[2]}  L={r[3]:>4}m  W={r[4]:>3}m  Name={r[1]}")

print("\n\n=== 中国 OperatorService 分布 (仅 Cat 9001 / Air Base) ===")
rows = list(cur.execute("""
    SELECT OperatorService, COUNT(*)
    FROM DataFacility
    WHERE OperatorCountry=2018 AND Category=9001 AND Deprecated='No'
    GROUP BY OperatorService
"""))
for r in rows: print(" Service=", r[0], " count=", r[1])

print("\n=== 中国仅 Cat=9001 的机场列表 ===")
rows = list(cur.execute("""
    SELECT ID, Name, OperatorService
    FROM DataFacility
    WHERE OperatorCountry=2018 AND Category=9001 AND Deprecated='No'
    ORDER BY Name
"""))
print(f"count: {len(rows)}")
for r in rows: print(f"  DBID={r[0]:>5}  Service={r[2]:>4}  Name={r[1]}")

con.close()
