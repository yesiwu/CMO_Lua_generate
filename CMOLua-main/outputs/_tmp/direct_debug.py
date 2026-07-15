import sqlite3
DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

# 直接打印
print("=== direct compare ===")
print(" WHERE 2018:", cur.execute("SELECT COUNT(*) FROM DataFacility WHERE OperatorCountry=2018").fetchone())
print(" WHERE 2018.0:", cur.execute("SELECT COUNT(*) FROM DataFacility WHERE OperatorCountry=2018.0").fetchone())
print(" WHERE = '2018':", cur.execute("SELECT COUNT(*) FROM DataFacility WHERE OperatorCountry='2018'").fetchone())

# DISTINCT values
print("\n=== distinct cast OperatorCountry as int ===")
print(cur.execute("SELECT DISTINCT CAST(OperatorCountry AS INT) FROM DataFacility ORDER BY 1").fetchall())

# 直接 emoji 调试
print("\n=== preview where OperatorCountry=2018 ===")
rows = cur.execute("SELECT ID, Name, OperatorCountry, typeof(OperatorCountry) FROM DataFacility WHERE OperatorCountry=2018 LIMIT 5").fetchall()
for r in rows: print(" ", r)

# 用 = 不带
print("\n=== ID + Name only ===")
rows = list(cur.execute("SELECT ID, Name, OperatorCountry FROM DataFacility WHERE ID IN (3,4,5)"))
for r in rows: print(" ", r)

# OperatorCountry 是空字符串?
print("\n=== look at head data ===")
rows = list(cur.execute("SELECT ID, Name, OperatorCountry, OperatorService FROM DataFacility LIMIT 10"))
for r in rows: print(" ", r)

# country 全 distinct 数字并存
print("\n=== all distinct OperatorCountry 头 30 (with COUNT) ===")
for r in cur.execute("SELECT DISTINCT OperatorCountry FROM DataFacility ORDER BY OperatorCountry LIMIT 30"):
    print(" type=", type(r[0]), " value=", r[0])

con.close()
