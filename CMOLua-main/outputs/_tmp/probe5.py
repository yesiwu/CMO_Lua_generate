import sqlite3

DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== LoadoutID 14059 详情 ===")
row = cur.execute("SELECT * FROM DataLoadout WHERE ID=14059").fetchone()
print(" meta:", row)
weapons = list(cur.execute(
    "SELECT lw.*, w.Name FROM DataLoadoutWeapons lw LEFT JOIN DataWeapon w ON w.ID=lw.ComponentID WHERE lw.ID=14059"
))
for w in weapons:
    print(" ", w)

print("\n=== LoadoutID 14059 关联了哪些平台? ===")
rows = list(cur.execute("SELECT * FROM DataAircraftLoadouts WHERE ID=14059"))
print(" count:", len(rows))
for r in rows:
    aid = r[1]
    nm = cur.execute("SELECT Name FROM DataAircraft WHERE ID=?", (aid,)).fetchone()
    print(" ", aid, "->", nm)

print("\n=== 哪些 Loadout 包含 YJ-83K (2137) ===")
rows = list(cur.execute(
    "SELECT DISTINCT lw.ID, dl.Name, dl.Comments FROM DataLoadoutWeapons lw JOIN DataLoadout dl ON dl.ID=lw.ID WHERE lw.ComponentID=2137"
))
print(" count:", len(rows))
for r in rows[:30]:
    # 找哪个平台用这个 Loadout
    plats = list(cur.execute("SELECT ComponentID FROM DataAircraftLoadouts WHERE ID=?", (r[0],)))
    pnames = []
    for pid in plats:
        nm = cur.execute("SELECT Name FROM DataAircraft WHERE ID=?", (pid[0],)).fetchone()
        if nm: pnames.append(f"{nm[0]} ({pid[0]})")
    print(" ", r, "  平台:", pnames[:5])

print("\n=== 哪些 Loadout 包含 YJ-18 (2868) ===")
rows = list(cur.execute(
    "SELECT DISTINCT lw.ID, dl.Name, dl.Comments FROM DataLoadoutWeapons lw JOIN DataLoadout dl ON dl.ID=lw.ID WHERE lw.ComponentID=2868"
))
print(" count:", len(rows))
for r in rows[:30]:
    plats = list(cur.execute("SELECT ComponentID FROM DataAircraftLoadouts WHERE ID=?", (r[0],)))
    pnames = []
    for pid in plats:
        nm = cur.execute("SELECT Name FROM DataAircraft WHERE ID=?", (pid[0],)).fetchone()
        if nm: pnames.append(f"{nm[0]} ({pid[0]})")
    print(" ", r, "  平台:", pnames[:5])

# 找 J-16 的 YJ-83 / YJ-18 实挂
print("\n=== J-16 (2853) 反舰挂载实际是哪些？ 查 v_name like J16 + 反舰弹 ===")
asm_weapons = [541, 2137, 2867, 2868, 3476, 3943, 4392]  # YJ-83/18/c-802A 全家
asm_names = []
for dbid in asm_weapons:
    nm = cur.execute("SELECT Name FROM DataWeapon WHERE ID=?", (dbid,)).fetchone()
    if nm: asm_names.append((dbid, nm[0]))

for w_dbid, w_name in asm_names:
    sql = """
        SELECT DISTINCT dal.ID, dl.Name
        FROM DataAircraftLoadouts dal
        JOIN DataLoadoutWeapons dlw ON dlw.ID = dal.ID
        JOIN DataLoadout dl ON dl.ID = dal.ID
        WHERE dal.ComponentID = 2853 AND dlw.ComponentID = ?
    """
    rows = list(cur.execute(sql, (w_dbid,)))
    if rows:
        print(f"  J-16 (2853) 包含 {w_name} ({w_dbid}): {rows}")

con.close()
