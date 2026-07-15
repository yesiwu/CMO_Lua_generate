import sqlite3, sys

DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== 1) Loadout related tables ===")
rows = list(cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND lower(name) LIKE '%loadout%'"))
for (name,) in rows:
    print(" ", name)
print(f"  total: {len(rows)}")

print("\n=== 2) Weapon related tables ===")
rows = list(cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND lower(name) LIKE '%weapon%'"))
for (name,) in rows:
    print(" ", name)
print(f"  total: {len(rows)}")

print("\n=== 3) Aircraft related tables (J-16 platform) ===")
rows = list(cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND lower(name) LIKE '%aircraft%'"))
for (name,) in rows:
    print(" ", name)
print(f"  total: {len(rows)}")

con.close()
