# A24场景 — 有限反击训练场景

## 概述

| 字段 | 值 |
|------|-----|
| 方案名称 | 有限反击训练场景 |
| 场景ID | zzcjxxxxxx0 |
| 版本 | 1.0 |
| 创建日期 | 2025-10-22 |
| 场景开始时间 | 2025/10/26 17:20:00 |
| 描述 | 东部方向进入战役阶段，蓝方在南部方向增强行动强度。蓝方驱护舰编队与我持续对峙，其火箭炮、中导部队进入战备状态；我无人干扰系统实施电磁压制，前沿防空系统进入高度戒备，潜艇部队实施机动部署。 |

## 阵营

| CMO 阵营名 | ForceSideID | 说明 |
|-----------|------------|------|
| 红方 | FORCE-SIDE-RED-001 | 红方部队 |
| 蓝方 | FORCE-SIDE-BLUE-001 | 蓝方部队 |

## 单位映射说明

### DBID 来源（MCP 查询结果）

| 装备类型 | JSON EquipmentType | MCP 查询关键词 | 找到 DBID | 备注 |
|---------|-------------------|---------------|-----------|------|
| J-16D 电子战 | AC_J16D | J-16D | 4632 | J-16D Roaring Wolf |
| J-20A 战斗机 | AC_J20 | J-20 | 5012 | J-20A Fagin (WS-10C) |
| J-16 战斗机 | AC_J16 | J-16 | 2853 | J-16 Flying Shark |
| 翼龙2无人机 | UAV_YILONG2D | Wing Loong II | 4725 | GJ-2 Wing Loong II UCAV (country 2018) |
| 长航时无人机 | UAV_LONG_ENDURANCE | MQ-4C Triton | 4939 | MQ-4C Triton (country 2035) |
| F-35B 闪电II | F35B | F-35B STOVL | 3870 | F-35B Lightning II STOVL |

### 跳过的单位（MCP 未找到匹配）

| 装备类型 | 数量 | 原因 |
|---------|------|------|
| SAT_JIANBING23 (卫星) | 50+ | CMO 数据库无卫星数据 |
| GND_DF17_LAUNCHER (DF-17 发射车) | 2 | 无精确匹配 |
| GND_DF26B_LAUNCHER (DF-26B 发射车) | 6 | 无精确匹配 |
| EW_YUNLEIGAN9 (云雷干9) | 1 | 无匹配 |
| BOMBER_H6K (H-6K 轰炸机) | 9 | H-6A/D 存在但 H-6K 无精确匹配 |
| AWACS_KJ500 (KJ-500 预警机) | 2 | 最接近 KJ-200 (DBID 2487) 但型号不同 |
| UUV_RED (潜艇/UUV) | 39 | 无精确匹配 |
| DDG_055 (055型驱逐舰) | 7 | 中国船只在数据库中极少见 |
| CVN_LINCOLN (航母) | 1 | 无匹配 |
| Ticonderoga (巡洋舰) | 2 | 无精确匹配 |
| DDG_CHAFEE (Burke 驱逐舰) | 5 | 最接近 DDG-84 (DBID 2869) |
| AUX_KZ_SUPPLY (补给舰) | 1 | 无匹配 |
| FFG_RICHMOND (护卫舰) | 1 | 无精确匹配 |
| LHA_AMERICA (两栖攻击舰) | 1 | 无匹配 |
| USV_OVERLORD (无人水面艇) | 6 | 无匹配 |
| AGOS_VICTORIOUS (监视船) | 3 | 无匹配 |
| AC_F35C_LIGHTNING (F-35C) | 4 | DBID 824 存在但挂载与场景需求不匹配 |

### 可考虑替代方案

- **DDG_055** → Type 052D (052D destroyer) 可能在数据库中，请手动验证
- **CVN_LINCOLN** → Nimitz class carrier 可能存在，请手动查询
- **DDG_CHAFEE** → DDG-84 USS Chafee (DBID 2869) 可作为近似替代
- **Ticonderoga** → CG-59 Princeton (DBID 599/2126) 有 SM-3/Aegis BMD
- **F-35C** → F-35C Lightning II (DBID 824) 可用，但需手动指定 LoadoutID

## LoadoutID 说明

所有飞机单位（`type = "Aircraft"`）均需要 `LoadoutID` 参数。
当前脚本中所有飞机的 `LoadoutID` 标注为 `[TODO: LoadoutID]`，需通过以下 SQL 查询：

```sql
-- 示例：查询 J-16D (DBID 4632) 的可用 LoadoutID
SELECT LoadoutID, Name, Description
FROM DataAircraftLoadouts
WHERE ComponentID = 4632;
```

请在运行脚本前补全所有飞机的 LoadoutID，否则飞机将不携带任何武器。

## 使用方法

1. 在 CMO 中打开或创建场景
2. 在编辑器 Lua 控制台中粘贴 `main.lua` 的内容，或通过事件脚本执行
3. 补全所有 `[TODO: LoadoutID]` 的数值
4. 运行脚本，检查控制台输出

## 跳过的单位处理建议

对于跳过的单位，可以：
1. 在 CMO 编辑器中手动添加这些单位
2. 使用近似的 CMO 数据库装备替代（如上表所示）
3. 等待 CMO 数据库更新后重新生成
