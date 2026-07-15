import sqlite3
con = sqlite3.connect(r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3")   # 换成真实路径
cur = con.cursor()

AIRCRAFT_DBID = 2853
WANT = 541   # YJ-83

def rows(sql, args=()):
    return cur.execute(sql, args).fetchall()

# 可选:武器 dbid → 名称(表名猜 DataWeapon,失败就只显示 dbid)
wname = {}
try:
    for wid, nm in rows("SELECT ID, Name FROM DataWeapon"):
        wname[wid] = nm
except Exception:
    pass
def wl(wid):
    return f"{wid}" + (f"({wname[wid]})" if wid in wname else "")

# 1) J-16 的挂载 ID(自动判方向)
lids = [r[0] for r in rows("SELECT ComponentID FROM DataAircraftLoadouts WHERE ID=?", (AIRCRAFT_DBID,))]
if not lids:
    lids = [r[0] for r in rows("SELECT ID FROM DataAircraftLoadouts WHERE ComponentID=?", (AIRCRAFT_DBID,))]
print(f"J-16(dbid={AIRCRAFT_DBID}) 挂载数 = {len(lids)}\n")

# 2) 逐挂载展开
hits = []
for lid in lids:
    r = rows("SELECT Name, LoadoutRole, Capacity FROM DataLoadout WHERE ID=?", (lid,))
    name, role = (r[0][0], r[0][1]) if r else ("?", "?")
    w = [x[0] for x in rows("SELECT ComponentID FROM DataLoadoutWeapons WHERE ID=?", (lid,))]
    if not w:
        w = [x[0] for x in rows("SELECT ID FROM DataLoadoutWeapons WHERE ComponentID=?", (lid,))]
    has = WANT in w
    if has: hits.append((lid, name))
    print(f"[{lid}] {name} (role={role}){'  <<< 含541' if has else ''}")
    print("     weapons = " + ", ".join(wl(x) for x in w))

print("\n==== 含 YJ-83(541) 的挂载 ====")
if hits:
    for lid, name in hits:
        print(f"LOADOUT_ID = {lid}   # {name}")
else:
    print("无。541 很可能是舰射版;J-16 空射反舰多半是 YJ-83K / YJ-91,dbid 不同。")
    print("从上面挑名字带 AShM/YJ/anti-ship 的挂载,LOADOUT_ID 填它,")
    print("WEAPON_DBID 改成该挂载里那枚反舰弹的实际 dbid。")