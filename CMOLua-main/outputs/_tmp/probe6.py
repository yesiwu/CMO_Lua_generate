import sqlite3

DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

ids = [8303, 5325, 5367]
for dbid in ids:
    row = cur.execute("SELECT * FROM DataWeapon WHERE ID=?", (dbid,)).fetchone()
    print(f"=== DBID={dbid} ===")
    print(" ", row)
    print()

# WpnCount (弹的数量) 找出来 - 这列在 DataLoadoutWeapons 没有，需要 DataLoadout
# 看 DataLoadoutWeapons 的所有列
print("=== DataLoadoutWeapons complete schema ===")
for row in cur.execute("PRAGMA table_info(DataLoadoutWeapons)"):
    print(" ", row)

# 看另一个挂载机制 - 可能 DataAircraftMounts + DataMountWeapons 才是真相
print("\n=== DataAircraftMounts schema ===")
for row in cur.execute("PRAGMA table_info(DataAircraftMounts)"):
    print(" ", row)

print("\n=== DataMountWeapons schema ===")
for row in cur.execute("PRAGMA table_info(DataMountWeapons)"):
    print(" ", row)

# 看 J-16 的挂架结构
print("\n=== J-16 (2853) 挂架列表 ===")
rows = list(cur.execute("SELECT * FROM DataAircraftMounts WHERE ComponentID=2853"))
for r in rows:
    print(" ", r)

con.close()
