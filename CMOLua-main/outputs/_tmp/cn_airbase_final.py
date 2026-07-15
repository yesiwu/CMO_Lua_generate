import sqlite3
DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== OperatorCountry=2018 (China) 的所有 Cat in (2001,2002,2003,9001) ===")
rows = list(cur.execute("""
    SELECT ID, Name, Category, OperatorService, Length, Width
    FROM DataFacility
    WHERE OperatorCountry=2018
      AND Category IN (2001, 2002, 2003, 9001)
    ORDER BY Category, Length DESC
"""))
print(f"Total: {len(rows)}")
from collections import defaultdict
b = defaultdict(list)
for r in rows: b[r[2]].append(r)
for cat in sorted(b):
    print(f"\n--- Category={cat} (count={len(b[cat])}) ---")
    for r in b[cat]:
        print(f"  DBID={r[0]:>5} Svc={r[3]:>4} L={r[4]:>4}m W={r[5]:>3}m  {r[1]}")

print("\n\n=== China 所有 200 个设施按 Type 分布 top 30 ===")
rows = list(cur.execute("SELECT Type, COUNT(*) FROM DataFacility WHERE OperatorCountry=2018 AND Deprecated=0 GROUP BY Type ORDER BY 2 DESC LIMIT 30"))
for r in rows: print(" Type=", r[0], " n=", r[1])

con.close()
