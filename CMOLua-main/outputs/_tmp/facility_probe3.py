import sqlite3

DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

# 找所有中国 category=9001 (Air Base)
print("=== 中国 (Country=2018) Air Base (Category=9001) ===")
rows = list(cur.execute("SELECT ID, Name, Type FROM DataFacility WHERE OperatorCountry=2018 AND Category=9001 AND Deprecated='No' ORDER BY Name"))
print(f" count: {len(rows)}")
for r in rows:
    print(" ", r)

# 也看一下中国的 Runway 类
print("\n=== 中国 (2018) Runway (Category=2001) 头 30 ===")
rows = list(cur.execute("SELECT ID, Name, Type, Length, Width FROM DataFacility WHERE OperatorCountry=2018 AND Category=2001 AND Deprecated='No' ORDER BY Length DESC LIMIT 30"))
for r in rows:
    print(" ", r)

# 看看中国 OperatorService 都有哪些
print("\n=== EnumOperatorService (中国有哪些军种) ===")
rows = list(cur.execute("SELECT * FROM EnumOperatorService"))
for r in rows[:30]:
    print(" ", r)

# 看 China 各 Category 计数
print("\n=== 中国 Facility 按 Category 计数 ===")
rows = list(cur.execute("SELECT Category, COUNT(*) FROM DataFacility WHERE OperatorCountry=2018 AND Deprecated='No' GROUP BY Category ORDER BY Category"))
for r in rows:
    print(" Cat=", r[0], " count=", r[1])

con.close()
