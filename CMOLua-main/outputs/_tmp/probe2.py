import sqlite3

DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== A) J-16 平台 (含 Flying Shark 等变体) ===")
rows = list(cur.execute(
    "SELECT ID, Name FROM DataAircraft WHERE Name LIKE '%J-16%' OR Name LIKE '%J16%' OR Name LIKE '%Flying Shark%' ORDER BY ID"
))
for r in rows:
    print(" ", r)

print("\n=== B) 鹰击-83 SKU ===")
rows = list(cur.execute(
    "SELECT ID, Name FROM DataWeapon WHERE Name LIKE '%YJ-83%' OR Name LIKE '%YJ83%' OR Name LIKE '%鹰击-83%' OR Name LIKE '%C-803%' OR Name LIKE '%C803%' ORDER BY ID"
))
for r in rows:
    print(" ", r)

print("\n=== C) 鹰击-18 SKU ===")
rows = list(cur.execute(
    "SELECT ID, Name FROM DataWeapon WHERE Name LIKE '%YJ-18%' OR Name LIKE '%YJ18%' OR Name LIKE '%鹰击-18%' ORDER BY ID"
))
for r in rows:
    print(" ", r)

print("\n=== D) DataLoadoutWeapons schema ===")
for row in cur.execute("PRAGMA table_info(DataLoadoutWeapons)"):
    print(" ", row)

print("\n=== E) LoadoutID=14059 内容 ===")
rows = list(cur.execute("PRAGMA table_info(DataLoadoutWeapons)"))
cols = [r[1] for r in rows]
print("  cols:", cols)
rows = list(cur.execute("SELECT * FROM DataLoadoutWeapons WHERE LoadoutID=14059 LIMIT 30"))
print("  row count:", len(rows))
for r in rows[:30]:
    print(" ", r)

print("\n=== F) LoadoutID=1821 内容 (SKILL.md 模板示例) ===")
rows = list(cur.execute("SELECT * FROM DataLoadoutWeapons WHERE LoadoutID=1821 LIMIT 30"))
print("  row count:", len(rows))
for r in rows[:30]:
    print(" ", r)

print("\n=== G) DataAircraftLoadouts schema ===")
for row in cur.execute("PRAGMA table_info(DataAircraftLoadouts)"):
    print(" ", row)

print("\n=== H) J-16 平台 (ID=2853) 的所有 LoadoutID 列表 ===")
rows = list(cur.execute(
    "SELECT * FROM DataAircraftLoadouts WHERE ComponentID=2853"
))
print("  count:", len(rows))
for r in rows[:20]:
    print(" ", r)

con.close()
