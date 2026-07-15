import sqlite3

DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== 1) DataFacility schema ===")
for row in cur.execute("PRAGMA table_info(DataFacility)"):
    print(" ", row)
print()
print("=== 2) DataFacilityCodes schema (国家关联) ===")
for row in cur.execute("PRAGMA table_info(DataFacilityCodes)"):
    print(" ", row)
print()
print("=== 3) EnumOperatorCountry schema ===")
for row in cur.execute("PRAGMA table_info(EnumOperatorCountry)"):
    print(" ", row)
print()
print("=== 4) EnumFacilityType schema ===")
for row in cur.execute("PRAGMA table_info(EnumFacilityType)"):
    print(" ", row)

con.close()
