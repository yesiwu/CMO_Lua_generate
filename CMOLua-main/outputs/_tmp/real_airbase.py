import sqlite3
DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== facility-related tables ===")
for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND (lower(name) LIKE '%facil%' OR lower(name) LIKE '%airport%' OR lower(name) LIKE '%airbase%')"):
    print(" ", r[0])

# 看 DataFacilityAircraftFacilities - 上次我看到的是 (ID, ComponentNumber, ComponentID)，
# 这是 "ComponentID (设施) 包含 ComponentNumber (飞机 ID)" —— 设施可以容纳哪些飞机
print("\n=== DataFacilityAircraftFacilities sample ===")
rows = list(cur.execute("SELECT * FROM DataFacilityAircraftFacilities LIMIT 10"))
for r in rows: print(" ", r)

# 试几个低 ID 是机场类
print("\n=== 看个 (DBID=200, 240) 这种常见 airport 设施 ===")
for fid in [200, 240, 300, 350, 400, 450, 500, 600, 700, 800, 900]:
    name = cur.execute("SELECT Name, Category FROM DataFacility WHERE ID=?", (fid,)).fetchone()
    if name: print(f"  DBID={fid} {name}")

# 看 F-16C (124) 可以停哪些设施
print("\n=== F-16C (124) 能停的设施 ===")
rows = list(cur.execute("""
    SELECT DISTINCT f.ID, f.Name, f.Category
    FROM DataFacilityAircraftFacilities faf
    JOIN DataFacility f ON f.ID = faf.ID
    WHERE faf.ComponentID = 124
    LIMIT 30
"""))
for r in rows: print(" ", r)

# 看中国 DBID 的 FBCB 和 FCR 等机型
print("\n=== J-16 (2853) 的 DataFacilityAircraftFacilities ===")
rows = list(cur.execute("""
    SELECT DISTINCT f.ID, f.Name, f.Category
    FROM DataFacilityAircraftFacilities faf
    JOIN DataFacility f ON f.ID = faf.ID
    WHERE faf.ComponentID = 2853
    LIMIT 30
"""))
print(f" count: {len(rows)}")
for r in rows: print(" ", r)

con.close()
