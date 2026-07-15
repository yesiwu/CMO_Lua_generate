import sqlite3

DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== 1) DataLoadout schema ===")
for row in cur.execute("PRAGMA table_info(DataLoadout)"):
    print(" ", row)

print("\n=== 2) DataAircraftLoadouts schema ===")
for row in cur.execute("PRAGMA table_info(DataAircraftLoadouts)"):
    print(" ", row)

print("\n=== 3) DataLoadout 表前 5 行 ===")
for row in cur.execute("SELECT * FROM DataLoadout LIMIT 5"):
    print(" ", row)

print("\n=== 4) DataAircraftLoadouts 表前 5 行 ===")
for row in cur.execute("SELECT * FROM DataAircraftLoadouts LIMIT 5"):
    print(" ", row)

# 找 J-16 (2853) 的 loadout
print("\n=== 5) J-16 (ID=2853) 在 DataAircraftLoadouts ===")
rows = list(cur.execute("SELECT * FROM DataAircraftLoadouts WHERE ComponentID=2853"))
print(" count:", len(rows))
for r in rows[:30]:
    print(" ", r)

# 看 J-16D (4632)
print("\n=== 6) J-16D (ID=4632) 在 DataAircraftLoadouts ===")
rows = list(cur.execute("SELECT * FROM DataAircraftLoadouts WHERE ComponentID=4632"))
print(" count:", len(rows))
for r in rows[:30]:
    print(" ", r)

# DataLoadoutWeapons 看是否有指向 Loadout 的 ComponentID/ComponentNumber
print("\n=== 7) DataLoadoutWeapons 行数 / 唯一样本 (前 10 行) ===")
n = cur.execute("SELECT COUNT(*) FROM DataLoadoutWeapons").fetchone()[0]
print(" total rows:", n)
for row in cur.execute("SELECT * FROM DataLoadoutWeapons LIMIT 10"):
    print(" ", row)

# DataLoadout 表 ID/编号
print("\n=== 8) DataLoadout 主键是 ID 还是? 头 10 行 ID ===")
for row in cur.execute("SELECT ID FROM DataLoadout LIMIT 10"):
    print(" ", row)

con.close()
