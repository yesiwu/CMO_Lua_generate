import sqlite3
DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

# 看 DataAircraftFacility 表 schema
print("=== DataAircraftFacility schema ===")
for r in cur.execute("PRAGMA table_info(DataAircraftFacility)"):
    print(" ", r)

print("\n=== DataAircraftFacility rows ===")
rows = list(cur.execute("SELECT * FROM DataAircraftFacility LIMIT 10"))
for r in rows: print(" ", r)
print(f" total rows: {cur.execute('SELECT COUNT(*) FROM DataAircraftFacility').fetchone()[0]}")

print("\n=== DataAircraftFacility distinct (ID, Cat_Length) ===")
n = cur.execute("SELECT COUNT(*) FROM DataAircraftFacility").fetchone()[0]
print(f" total: {n}")

# 看 ID=100+ 的
print("\n=== DataAircraftFacility where ID>500 (前 20) ===")
rows = list(cur.execute("SELECT * FROM DataAircraftFacility WHERE ID>500 LIMIT 20"))
for r in rows: print(" ", r)

# distinct runways? 看 length 列
print("\n=== DataAircraftFacility lengths (runways) ===")
rows = list(cur.execute("SELECT DISTINCT ID FROM DataAircraftFacility ORDER BY ID"))
print(f" distinct IDs: {len(rows)}")
print(rows[:30])

con.close()
