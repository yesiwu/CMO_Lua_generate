import sqlite3
DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

# 看中国 (2018) 的 Category 分布
print("=== China (2018) by Category ===")
rows = list(cur.execute("""
    SELECT Category, COUNT(*) FROM DataFacility
    WHERE OperatorCountry=2018 AND Deprecated=0
    GROUP BY Category ORDER BY 2 DESC
"""))
for r in rows: print(" Cat=", r[0], " count=", r[1])

# 看 2018 名字含 "Air" "Airport" "Airfield" "Base"
print("\n=== China 名字含 Air/Base/Port ===")
rows = list(cur.execute("""
    SELECT ID, Name, Category, OperatorService, Length, Width
    FROM DataFacility
    WHERE OperatorCountry=2018
      AND (Name LIKE '%ir%' OR Name LIKE '%ase%' OR Name LIKE '%irport%' OR Name LIKE '%irfield%')
    ORDER BY Category, Name
"""))
print(f" count: {len(rows)}")
for r in rows[:50]:
    print(f"  DBID={r[0]} Cat={r[2]} Svc={r[3]} L={r[4]}W={r[5]}  {r[1]}")

con.close()
