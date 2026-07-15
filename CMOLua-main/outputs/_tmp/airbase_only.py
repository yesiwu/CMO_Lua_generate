import sqlite3
DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== OperatorCountry=2018 Cat=9001 (Air Base 类别) 中国机场 ===")
rows = list(cur.execute("""
    SELECT ID, Name, Type, OperatorService, Length, Width
    FROM DataFacility
    WHERE OperatorCountry=2018
      AND Category=9001
      AND Deprecated=0
    ORDER BY Name
"""))
print(f"Total: {len(rows)}\n")
for r in rows:
    print(f"  DBID={r[0]:>5} Type={r[2]:>4} Svc={r[3]:>4} L={r[4]:>4}m W={r[5]:>3}m  {r[1]}")

# 还看按 Service 分桶
print("\n=== OperatorCountry=2018 Cat=9001 by Service ===")
rows = list(cur.execute("""
    SELECT OperatorService, COUNT(*) FROM DataFacility
    WHERE OperatorCountry=2018 AND Category=9001 AND Deprecated=0
    GROUP BY OperatorService
"""))
for r in rows: print(" Service=", r[0], " count=", r[1])

con.close()
