import sqlite3
DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== EnumFacilityType 全部 ===")
for r in cur.execute("SELECT ID, Description FROM EnumFacilityType ORDER BY ID"):
    print(f"  {r[0]:>5}  {r[1]}")

print("\n=== EnumFacilityCategory 全部 ===")
for r in cur.execute("SELECT ID, Description FROM EnumFacilityCategory ORDER BY ID"):
    print(f"  {r[0]:>5}  {r[1]}")

# 看中国跑道 (Type=2001) 的 10 个 sample
print("\n=== China Type=2001 (前 10) ===")
rows = list(cur.execute("SELECT ID, Name, Category, Type, OperatorService, Length, Width FROM DataFacility WHERE OperatorCountry=2018 AND Type=2001 LIMIT 10"))
for r in rows: print(" ", r)

# 单独看中国 "2001" 跑道设施名称
print("\n=== China Type=2001 全部，按长度降序 ===")
rows = list(cur.execute("SELECT ID, Name, OperatorService, Length, Width FROM DataFacility WHERE OperatorCountry=2018 AND Type=2001 ORDER BY Length DESC"))
print(f" count: {len(rows)}")
for r in rows:
    print(f"  DBID={r[0]:>5} Svc={r[2]:>4} L={r[3]:>4}m W={r[4]:>3}m  {r[1]}")

# China Type=9001
print("\n=== China Type=9001 全部 ===")
rows = list(cur.execute("SELECT ID, Name, Category, OperatorService FROM DataFacility WHERE OperatorCountry=2018 AND Type=9001 ORDER BY Name"))
print(f" count: {len(rows)}")
for r in rows:
    print(f"  DBID={r[0]} Cat={r[2]} Svc={r[3]}  {r[1]}")

con.close()
