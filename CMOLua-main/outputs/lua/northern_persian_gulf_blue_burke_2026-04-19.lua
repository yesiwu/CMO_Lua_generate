-- 在波斯湾北部添加一艘蓝方阿利伯克级驱逐舰
-- DBID 已通过本地 DB3K_504 数据库查询确认：
--   2867 = DDG 51 Arleigh Burke [Arleigh Burke Flight I]

local side_name = "Blue"
local ship_name = "USS Arleigh Burke #1"

-- 波斯湾北部海域，避开岸线取一个稳妥坐标
local latitude = "28.90"
local longitude = "49.10"

local side = VP_GetSide({Side = side_name})
if not side then
    ScenEdit_AddSide({name = side_name, posture = "F"})
    ScenEdit_SetSideOptions({
        side = side_name,
        awareness = "Normal",
        proficiency = "Regular"
    })
end

local existing = ScenEdit_GetUnit({
    side = side_name,
    unitname = ship_name
})

if existing then
    print("单位已存在: " .. ship_name)
else
    local ship = ScenEdit_AddUnit({
        side = side_name,
        type = "Ship",
        name = ship_name,
        dbid = 2867,
        latitude = latitude,
        longitude = longitude,
        heading = 135,
        speed = 15
    })

    if ship then
        print("已添加蓝方阿利伯克级驱逐舰: " .. ship_name)
    else
        print("添加失败: " .. ship_name)
    end
end
