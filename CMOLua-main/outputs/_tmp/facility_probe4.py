import sqlite3

DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== EnumOperatorCountry 全部 ===")
rows = list(cur.execute("SELECT * FROM EnumOperatorCountry ORDER BY ID"))
for r in rows:
    print(" ", r)

# 数据条数
print("\n=== DataFacility 总条数 ===")
n = cur.execute("SELECT COUNT(*) FROM DataFacility").fetchone()[0]
print(" ", n)

# 按 Country 计数
print("\n=== DataFacility 按 OperatorCountry 计数 top 20 ===")
rows = list(cur.execute("SELECT OperatorCountry, COUNT(*) AS n FROM DataFacility WHERE Deprecated='No' GROUP BY OperatorCountry ORDER BY n DESC LIMIT 20"))
for r in rows:
    print(" Country=", r[0], " n=", r[1])

# 看看 Country=2018 在表里能匹配吗
print("\n=== 验证 Country=2018 在 DataFacility 是否真的 0 条 ===")
n = cur.execute("SELECT COUNT(*) FROM DataFacility WHERE OperatorCountry=2018").fetchone()[0]
print(" 2018 count (any):", n)
n = cur.execute("SELECT COUNT(*) FROM DataFacility WHERE OperatorCountry=2018 AND Deprecated='No'").fetchone()[0]
print(" 2018 non-deprecated:", n)

# 看一个已知中国装备的 Country
print("\n=== 验证 J-16 (2853) 的 Country ===")
rows = list(cur.execute("SELECT * FROM DataAircraftCodes WHERE ComponentID=2853"))
for r in rows:
    print(" ", r)
# DataAircraft 表
print("\n=== DataAircraft schema ===")
for row in cur.execute("PRAGMA table_info(DataAircraft)"):
    print(" ", row)

# DataAircraftCodes
print("\n=== DataAircraftCodes schema ===")
for row in cur.execute("PRAGMA table_info(DataAircraftCodes)"):
    print(" ", row)

con.close()
