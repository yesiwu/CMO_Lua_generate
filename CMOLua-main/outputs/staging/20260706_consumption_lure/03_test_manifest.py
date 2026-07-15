"""Test manifest.lua via dofile (CMO Console compatible)"""
import subprocess
import os

env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"

# Note: This script generates a test file to be pasted into CMO Lua Console.
# In CMO, use dofile() to load manifest.lua, NOT require().
# Copy-paste the output into CMO Lua Console.

manifest_dir = r"C:\Users\user\.codex\skills\CMOLua-main\outputs\lua\20260706_101200_consumption_lure"
manifest_path = os.path.join(manifest_dir, "manifest.lua")

test_script = f"""-- ============================================================
-- manifest.lua 自检脚本（粘贴到 CMO Lua Console 执行）
-- ============================================================
dofile("{manifest_path}")

print("[TEST] UNITS count = " .. tostring((function()
    local n=0 for _ in pairs(UNITS) do n=n+1 end return n
end)()))
print("[TEST] CLEAR_LIST count = " .. tostring(#CLEAR_LIST))
print("[TEST] AMMO count = " .. tostring(#AMMO))
print("[TEST] STRIKE count = " .. tostring(#STRIKE))
print("[TEST] PATROLS count = " .. tostring(#PATROLS))

-- 自检 Aircraft loadout_id
print("")
print("[TEST] Aircraft loadout_id 自检:")
for uid, u in pairs(UNITS) do
    if u.type == "Aircraft" then
        if u.loadout_id then
            print(string.format("  [PASS] %s loadout_id=%s", uid, tostring(u.loadout_id)))
        else
            print(string.format("  [FAIL] %s 缺少 loadout_id!", uid))
        end
    end
end

-- 打印 STRIKE 详情
print("")
print("[TEST] STRIKE 详情:")
for i, s in ipairs(STRIKE) do
    print(string.format("  [%d] %s -> %s wpn=%s qty=%s delay=%ss",
        i, s.attacker, s.target,
        tostring(s.wpn_dbid), tostring(s.qty), tostring(s.startDelay)))
end
"""

test_path = os.path.join(manifest_dir, "_test.lua")
with open(test_path, 'w', encoding='utf-8') as f:
    f.write(test_script)
print(f"Test file written: {test_path}")
print()
print("=== 使用方法 ===")
print(f"1. 打开 CMO Lua Console (Ctrl+L)")
print(f"2. 粘贴 _test.lua 内容并运行")
print("3. 检查 [TEST] 输出，确认 Aircraft loadout_id 全部 PASS")