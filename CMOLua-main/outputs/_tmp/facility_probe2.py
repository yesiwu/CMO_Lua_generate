import sqlite3

DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== 1) EnumOperatorCountry — 含 China/PRC 的条目 ===")
rows = list(cur.execute("SELECT * FROM EnumOperatorCountry WHERE Description LIKE '%hina%' OR Description LIKE '%PRC%'"))
for r in rows:
    print(" ", r)
print()

print("=== 2) EnumFacilityType — 机场类 ===")
rows = list(cur.execute("SELECT * FROM EnumFacilityType WHERE Description LIKE '%ir%' OR Description LIKE '%AF%' OR Description LIKE '%ield%'"))
for r in rows:
    print(" ", r)
print()

print("=== 3) EnumFacilityCategory ===")
rows = list(cur.execute("SELECT * FROM EnumFacilityCategory"))
for r in rows:
    print(" ", r)
print()

# 取中国 ID
cn = cur.execute("SELECT ID, Description FROM EnumOperatorCountry WHERE Description LIKE '%hina%'").fetchall()
if cn:
    cn_id = cn[0][0]
    print(f"=== 4) OperatorCountry={cn_id} ({cn[0][1]}) 的所有 Facility（按 Type 分组）===")
    rows = list(cur.execute("SELECT Type, COUNT(*) FROM DataFacility WHERE OperatorCountry=? AND Deprecated='No' GROUP BY Type ORDER BY Type", (cn_id,)))
    for r in rows:
        print(" Type=", r[0], " count=", r[1])
    print()
    print("=== 5) 中国 Facility 头 60 条（按 Type + Name 排序） ===")
    for r in cur.execute("SELECT ID, Name, Type, OperatorService FROM DataFacility WHERE OperatorCountry=? AND Deprecated='No' ORDER BY Type, Name LIMIT 60", (cn_id,)):
        print(" ", r)
con.close()
