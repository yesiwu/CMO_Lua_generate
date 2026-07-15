import sqlite3
DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== DataFacilityAircraftFacilities schema ===")
for r in cur.execute("PRAGMA table_info(DataFacilityAircraftFacilities)"):
    print(" ", r)

print("\n=== DataAircraftFacilities schema (飞机->设施) ===")
for r in cur.execute("PRAGMA table_info(DataAircraftFacilities)"):
    print(" ", r)

# 看 F-16C 的"机场"绑定
print("\n=== F-16C (DBID ?) DataAircraftFacilities ===")
f16 = cur.execute("SELECT ID, Name FROM DataAircraft WHERE Name LIKE '%F-16C%' LIMIT 1").fetchone()
print(" F-16C:", f16)
if f16:
    rows = list(cur.execute("SELECT * FROM DataAircraftFacilities WHERE ComponentID=?", (f16[0],)))
    print(f" AircraftFacilities count: {len(rows)}")
    for r in rows[:5]: print(" ", r)
    # ComponentID=呢？解释为 FacilityDBID
    fac_ids = [r[1] for r in rows]
    print(" distinct facility ids:", set(fac_ids))

    placeholders = ",".join("?" * len(fac_ids))
    fns = list(cur.execute(f"SELECT ID, Name FROM DataFacility WHERE ID IN ({placeholders})", fac_ids))
    print(" facilities:")
    for f in fns:
        print(f"  DBID={f[0]} {f[1]}")
