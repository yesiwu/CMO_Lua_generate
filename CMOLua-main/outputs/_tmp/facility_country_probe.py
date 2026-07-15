import sqlite3
DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

# 1) 看设施的国家分布 top 20
print("=== DataFacility 按 OperatorCountry 计数 TOP 30 ===")
rows = list(cur.execute("""
    SELECT OperatorCountry, COUNT(*) AS n
    FROM DataFacility WHERE Deprecated='No'
    GROUP BY OperatorCountry ORDER BY n DESC LIMIT 30
"""))
for r in rows: print(" Country=", r[0], " n=", r[1])

# 2) 看一个具体非 2018 的设施的 OperatorCountry 是数字还是别的东西
print("\n=== 看一个高计数国家的设施样本 (OperatorCountry=最常见那个) ===")
most_common = cur.execute("""
    SELECT OperatorCountry, COUNT(*) AS n
    FROM DataFacility WHERE Deprecated='No'
    GROUP BY OperatorCountry ORDER BY n DESC LIMIT 1
""").fetchone()
sample = cur.execute("""
    SELECT ID, Name, OperatorCountry FROM DataFacility
    WHERE OperatorCountry=? AND Deprecated='No' LIMIT 10
""", (most_common[0],)).fetchall()
print(f"most common Country ID = {most_common[0]} ({most_common[1]} 条)")
for s in sample: print(" ", s)

# 3) 找含 China 的国家 ID（不固定为 2018）
print("\n=== 枚举任何 ID 含 China 关键词的国家 ===")
all_c = list(cur.execute("SELECT * FROM EnumOperatorCountry"))
for c in all_c:
    if 'hina' in c[1].lower() or 'PRC' in c[1]:
        print(" ", c)

# 4) 看 DataFacilityCodes 表结构
print("\n=== DataFacilityCodes schema ===")
try:
    for r in cur.execute("PRAGMA table_info(DataFacilityCodes)"):
        print(" ", r)
    rows = list(cur.execute("SELECT * FROM DataFacilityCodes LIMIT 5"))
    print(" head rows:")
    for r in rows: print(" ", r)
except Exception as e:
    print(" ERR:", e)

# 5) 看 DataFacilityCountries / DataFacilityAffiliations 之类关联表
print("\n=== 看是不是有 Country 关联表 ===")
for r in cur.execute("""SELECT name FROM sqlite_master WHERE type='table' AND lower(name) LIKE '%country%'"""):
    print(" ", r[0])

con.close()
