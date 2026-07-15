import sqlite3
DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

# 1) 快速验证国家=2018 的设施几条样本
print("=== Sample (DBID, Name, Category, Type, OperatorCountry, OperatorService, Length, Width) 国家=2018 ===")
rows = list(cur.execute("""
    SELECT ID, Name, Category, Type, OperatorCountry, OperatorService, Length, Width
    FROM DataFacility
    WHERE OperatorCountry=2018
      AND Deprecated='No'
    ORDER BY Category, Name
"""))
print(f"Total: {len(rows)}\n")
# 按 Category 分组打印
from collections import defaultdict
buckets = defaultdict(list)
for r in rows: buckets[r[2]].append(r)
for cat in sorted(buckets):
    print(f"\n--- Category={cat} ({len(buckets[cat])} 个) ---")
    for r in buckets[cat][:30]:
        print(f"  DBID={r[0]:>5} Type={r[3]:>4} Service={r[5]:>4} L={r[6]:>4} W={r[7]:>3}  {r[1]}")

# 2) 列出全部中国机场（Category=9001 仅 Air Base）
print("\n\n=== 仅 Category=9001 (Air Base) 的中国设施 ===")
rows = list(cur.execute("""
    SELECT ID, Name, Type, OperatorService
    FROM DataFacility WHERE OperatorCountry=2018 AND Category=9001 AND Deprecated='No'
    ORDER BY Name
"""))
print(f"count: {len(rows)}")
for r in rows:
    print(f"  DBID={r[0]:>5} Type={r[2]:>4} Service={r[3]:>4}  {r[1]}")

con.close()
