import sqlite3
DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

# 1) OperatorCountry 全部 distinct
print("=== DataFacility OperatorCountry distinct values ===")
rows = list(cur.execute("SELECT DISTINCT OperatorCountry FROM DataFacility ORDER BY OperatorCountry"))
for r in rows: print(" ", r[0])

# 2) DataShip / DataAircraft 的 country 分布对比
print("\n=== DataAircraft OperatorCountry distinct top 20 ===")
rows = list(cur.execute("SELECT OperatorCountry, COUNT(*) FROM DataAircraft GROUP BY OperatorCountry ORDER BY 2 DESC LIMIT 20"))
for r in rows: print(" Country=", r[0], " n=", r[1])

# 3) DataShip
print("\n=== DataShip OperatorCountry distinct top 20 ===")
rows = list(cur.execute("SELECT OperatorCountry, COUNT(*) FROM DataShip GROUP BY OperatorCountry ORDER BY 2 DESC LIMIT 20"))
for r in rows: print(" Country=", r[0], " n=", r[1])

# 4) EnumOperatorCountry 对照 ID
print("\n=== EnumOperatorCountry 头 30 ===")
for r in cur.execute("SELECT ID, Description FROM EnumOperatorCountry ORDER BY ID LIMIT 30"):
    print(" ", r)

# 5) facility 国家 ID 是 1001/1002/1003/1004 还是？
print("\n=== DataFacility 中 OperatorCountry>=2000 的 facility ===")
rows = list(cur.execute("SELECT OperatorCountry, COUNT(*) FROM DataFacility WHERE OperatorCountry>=2000 GROUP BY OperatorCountry ORDER BY OperatorCountry"))
for r in rows: print(" Country=", r[0], " n=", r[1])

con.close()
