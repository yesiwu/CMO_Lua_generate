import sqlite3

DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== LoadoutID 1821 详情 (J-16 / SKILL 模板用的) ===")
row = cur.execute("SELECT * FROM DataLoadout WHERE ID=1821").fetchone()
print(" meta:", row)
weapons = list(cur.execute("SELECT * FROM DataLoadoutWeapons WHERE ID=1821"))
print(" weapons rows:", len(weapons))
for w in weapons:
    wid = w[2]
    wname = cur.execute("SELECT Name FROM DataWeapon WHERE ID=?", (wid,)).fetchone()
    print(" ", w, "->", wname)

print("\n=== LoadoutID 3272 详情 (J-16 / 第 2 个挂载) ===")
row = cur.execute("SELECT * FROM DataLoadout WHERE ID=3272").fetchone()
print(" meta:", row)
weapons = list(cur.execute("SELECT * FROM DataLoadoutWeapons WHERE ID=3272"))
print(" weapons rows:", len(weapons))
for w in weapons:
    wid = w[2]
    wname = cur.execute("SELECT Name FROM DataWeapon WHERE ID=?", (wid,)).fetchone()
    print(" ", w, "->", wname)

# 14059 真不存在
print("\n=== 验证 LoadoutID=14059 不存在 ===")
n14059 = cur.execute("SELECT COUNT(*) FROM DataLoadout WHERE ID=14059").fetchone()[0]
print("  DataLoadout where ID=14059:", n14059)
n14059w = cur.execute("SELECT COUNT(*) FROM DataLoadoutWeapons WHERE ID=14059").fetchone()[0]
print("  DataLoadoutWeapons where ID=14059:", n14059w)

# 看包含 YJ-83K 的所有 Loadout
print("\n=== 包含 YJ-83K (DBID 2137) 的全部 LoadoutID ===")
rows = list(cur.execute(
    "SELECT DISTINCT ID FROM DataLoadoutWeapons WHERE ComponentID=2137"
))
print(" count:", len(rows))
for r in rows[:30]:
    print(" ", r[0])

# 看 J-16 (2853) 的 max/min LoadoutID 在 DataLoadoutWeapons
print("\n=== DataLoadoutWeapons 中 ID=1821/3272 总和 ===")
for lid in (1821, 3272):
    n = cur.execute("SELECT COUNT(*) FROM DataLoadoutWeapons WHERE ID=?", (lid,)).fetchone()[0]
    print(f"  ID={lid}: {n} 武器行")

con.close()
