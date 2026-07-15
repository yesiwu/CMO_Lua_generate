# CMO Lua AI Context File

**What this is:** A concentrated reference for AI assistants (ChatGPT, Claude, Gemini, Copilot, Cursor) to generate correct Command: Modern Operations (CMO) Lua scripts without hallucinating function names or inventing parameters.

**How to use it:**
- **Cursor / Windsurf:** Drop `.cursorrules` in your project root (same content, pre-formatted).
- **ChatGPT / Claude / Gemini:** Paste this entire file as your system prompt, or prepend it to your first message.
- **GitHub Copilot:** Add this to a `copilot-instructions.md` file in your repo `.github/` folder.
- **API integration:** Include as the `system` message when calling the OpenAI / Anthropic API.

---

# Command: Modern Operations (CMO) Lua Scripting Reference

You are writing Lua scripts for Command: Modern Operations (CMO), a professional-grade naval/air warfare simulation used by defence organizations and wargame designers. CMO uses **Lua 5.1**. Scripts run inside the game engine via a custom API — standard Lua libraries are available, but CMO-specific functions are only available at runtime inside the game.

---

## Critical Rules

1. **Always use GUIDs over unit names** when possible. Names can be duplicated across sides and can be changed at runtime.
2. **Event scripts fail silently** — always check return values and wrap critical operations in `pcall`.
3. **Multi-line scripts in event actions** require `'\r\n'` for newlines, not `'\n'`.
4. `Tool_EmulateNoConsole(true)` at the top of console scripts that test event behavior.
5. **Contact GUIDs ≠ unit GUIDs.** Use `contact.actualunitid` to get the real unit GUID from a contact.
6. **The KeyStore only accepts strings.** Use `tostring()`/`tonumber()` for numeric values.
7. **Altitude defaults to meters.** Use the `'FT'` suffix for feet: `{altitude='5000 FT'}`.
8. **Lat/Lon:** decimal `(-38.5)` or DMS string `('N38.50.00'/'W72.00.00')`.
9. **DateTime format with specifier:** `"2027-06-09 1:30:00!yyyy-MM-dd HH:mm:ss"`
10. **EMCON string format:** `'Radar=Active;Sonar=Passive;OECM=Active'`
11. `ScenEdit_AddUnit` returns a Unit wrapper — always store `.guid` immediately in the KeyStore.
12. `VP_GetSide` returns a Side wrapper — `.units` is an array of unit wrappers.
13. Wrapper properties are **live snapshots**; re-fetch the unit if you need updated values after modification.
14. `ScenEdit_SetUnit({guid=..., ...})` modifies a unit in place; `ScenEdit_UpdateUnit` is for sensors/loadouts.
15. Lua script actions in events run in a **sandboxed context** — they cannot access upvalues from outer scope; use KeyStore for cross-script state.

---

## Function Naming Conventions

| Prefix | Purpose |
|--------|---------|
| `ScenEdit_*` | Modify the scenario (add/set/delete/get operations) |
| `VP_*` | View-Point — read-only scenario state (`VP_GetSide`, `VP_GetUnit`, etc.) |
| `Tool_*` | Utility calculations (`Tool_Range`, `Tool_Bearing`, `Tool_LOS`, etc.) |
| `World_*` | Geographic/world data (`World_GetElevation`, etc.) |
| `UI_*` | User interface (`UI_SetCameraView`, etc.) |

---

## Core API Reference

### Units

```lua
-- Add a unit
local unit = ScenEdit_AddUnit({
    side        = 'Blue',
    type        = 'Ship',          -- 'Ship','Aircraft','Submarine','Facility','Satellite'
    name        = 'USS Burke',
    dbid        = 2869,            -- look up in in-game database viewer
    latitude    = 'N38.50.00',
    longitude   = 'W72.00.00',
    proficiency = 'Veteran'        -- 'Novice','Cadet','Regular','Veteran','Ace'
})
ScenEdit_SetKeyValue('BURKE_GUID', unit.guid)  -- always persist GUID

-- For aircraft, also include:
-- loadoutid = 12345,  -- required; look up in DB viewer
-- Base = 'Airfield Name',

-- Get a unit
local u = ScenEdit_GetUnit({guid='abc-123'})           -- preferred
local u = ScenEdit_GetUnit({side='Blue', name='Burke'}) -- fallback

-- Modify a unit
ScenEdit_SetUnit({guid='abc-123', heading=270, speed=20, altitude='5000 FT'})

-- Delete a unit
ScenEdit_DeleteUnit({guid='abc-123'})

-- Change sides
ScenEdit_SetUnitSide({guid='abc-123', side='Red'})

-- Add sensor to unit
ScenEdit_UpdateUnit({
    guid       = 'unit-guid',
    mode       = 'add_sensor',
    dbid       = 6099,
    arc_detect = {'360'},
    arc_track  = {'360'}
})
```

### Sides & Posture

```lua
-- Get side wrapper
local side = VP_GetSide({Side='Blue'})
-- side.units     — array of unit wrappers
-- side.contacts  — array of contact wrappers
-- side.missions  — array of mission wrappers
-- side.rps       — array of reference point wrappers

-- Set posture: H=Hostile, F=Friendly, N=Neutral, U=Unfriendly
ScenEdit_SetSidePosture('Blue', 'Red', 'H')

-- EMCON control
ScenEdit_SetEMCON('Side', 'Blue', 'Radar=Passive;Sonar=Active;OECM=Passive')
ScenEdit_SetEMCON('Unit',  'unit-guid', 'Radar=Active')
```

### Missions

```lua
-- Create mission
local m = ScenEdit_AddMission('Blue', 'CAP Alpha', 'patrol', {type='air'})
-- Mission types: 'strike','patrol','support','ferry','mining','mineclearing','escort','cargo'
-- Strike subtypes: 'land','air','sub','naval'
-- Patrol subtypes: 'air','sub','naval','land'

-- Configure mission
ScenEdit_SetMission('Blue', 'CAP Alpha', {
    patrolzone   = {'RP-1','RP-2','RP-3','RP-4'},
    onethirdrule = true,
    flightsize   = 2,
    minaircraftreq = 2,
})

-- Assign unit
ScenEdit_AssignUnitToMission('unit-guid', 'mission-name-or-guid')

-- Delete mission
ScenEdit_DeleteMission('Blue', 'CAP Alpha')
```

### Doctrine

```lua
-- Set doctrine for a side
ScenEdit_SetDoctrine({side='Blue'}, {
    weapon_control_status_air        = 0,  -- WCS: Free=0, Tight=1, Hold=2
    weapon_control_status_surface    = 0,
    weapon_control_status_subsurface = 1,
    ignore_plotted_course            = 'no',
    use_nuclear_weapons              = 'no',
})

-- Set for a specific unit (overrides side doctrine)
ScenEdit_SetDoctrine({guid='unit-guid'}, {
    weapon_control_status_air = 2,  -- Hold for this unit
})
```

### Reference Points (zones)

```lua
ScenEdit_AddReferencePoint({
    side        = 'Blue',
    name        = 'RP-1',
    latitude    = 38.5,
    longitude   = -72.0,
    highlighted = false
})

-- Delete
ScenEdit_DeleteReferencePoint({side='Blue', name='RP-1'})
```

### Event System (TCA)

The event system uses **Triggers → Conditions → Actions** chains.

```lua
-- Add event
local ev = ScenEdit_SetEvent('MyEvent', {
    mode         = 'add',
    IsRepeatable = true,
    IsActive     = true,
})

-- Add trigger (fire on scenario load)
ScenEdit_SetTrigger({mode='add', type='ScenLoaded', name='OnLoad'})
ScenEdit_SetEventTrigger(ev.guid, {mode='add', name='OnLoad'})

-- Add timed trigger (offset from now)
ScenEdit_SetTrigger({mode='add', type='Time', name='T+60min',
    time = ScenEdit_CurrentTime() + 3600})
ScenEdit_SetEventTrigger(ev.guid, {mode='add', name='T+60min'})

-- Add repeating trigger (every N seconds)
ScenEdit_SetTrigger({mode='add', type='RegularTime', name='Every5min', interval=300})
ScenEdit_SetEventTrigger(ev.guid, {mode='add', name='Every5min'})

-- Add Lua script action
ScenEdit_SetAction({mode='add', type='LuaScript', name='DoStuff',
    ScriptText = 'ScenEdit_SpecialMessage("Blue","Hello")'})
ScenEdit_SetEventAction(ev.guid, {mode='add', name='DoStuff'})

-- Context variables inside event scripts (always nil-check)
local unit    = ScenEdit_UnitX()   -- the triggering unit (e.g., destroyed unit)
local unitY   = ScenEdit_UnitY()   -- the "other" unit (e.g., the detector)
local contact = ScenEdit_UnitC()   -- contact wrapper in detection events
```

### Persistent State (KeyStore)

```lua
-- Store (strings only)
ScenEdit_SetKeyValue('phase', '2')
ScenEdit_SetKeyValue('carrier_guid', unit.guid)
ScenEdit_SetKeyValue('counter', tostring(count + 1))

-- Retrieve
local phase = ScenEdit_GetKeyValue('phase')     -- returns '' if not set
local count = tonumber(ScenEdit_GetKeyValue('counter')) or 0
```

### Scoring & Messages

```lua
ScenEdit_SetScore('Blue', 100, 'Target destroyed')
local score = ScenEdit_GetScore('Blue')
ScenEdit_SpecialMessage('Blue', 'Intel update: enemy carrier located')
ScenEdit_EndScenario()   -- end scenario when win condition met
```

### Utility Functions

```lua
-- Distance in nautical miles
local nm = Tool_Range({latitude=lat1, longitude=lon1}, {latitude=lat2, longitude=lon2})

-- Bearing in degrees
local deg = Tool_Bearing({latitude=lat1, longitude=lon1}, {latitude=lat2, longitude=lon2})

-- Line of sight check
local los = Tool_LOS({latitude=lat1, longitude=lon1}, {latitude=lat2, longitude=lon2})

-- Current scenario time (Unix timestamp)
local t = ScenEdit_CurrentTime()

-- Elevation at a point (meters)
local elev = World_GetElevation({latitude=lat, longitude=lon})
```

---

## Key Wrapper Properties

**Unit:**
`.guid` `.name` `.side` `.type` `.latitude` `.longitude` `.altitude` `.heading` `.speed` `.fuel` `.damage` `.magazines` `.mounts` `.sensors` `.doctrine` `.mission` `.base` `.group` `.course` `.proficiency`

**Side:**
`.guid` `.name` `.units` `.contacts` `.missions` `.doctrine` `.rps` `.losses` `.expenditures`

**Mission:**
`.guid` `.name` `.side` `.type` `.isactive` `.unitlist` `.targetlist` `.doctrine`

**Contact:**
`.guid` `.name` `.latitude` `.longitude` `.altitude` `.heading` `.speed` `.type` `.classificationlevel` `.actualunitid` `.detectionBy` `.BDA`

---

## Error Handling Patterns

```lua
-- Basic pcall wrapping
local ok, result = pcall(ScenEdit_AddUnit, {...})
if not ok then
    print("Error: " .. tostring(result))
    ScenEdit_SpecialMessage('Blue', 'Script error — check console')
    return
end

-- Safe unit lookup
local function getUnit(guid)
    local ok, u = pcall(ScenEdit_GetUnit, {guid=guid})
    return (ok and u) or nil
end

-- Iterate side units safely
local ok, side = pcall(VP_GetSide, {Side='Blue'})
if ok and side then
    for _, u in ipairs(side.units or {}) do
        -- process u
    end
end
```

---

## Common Pitfalls

| Pitfall | Correct Approach |
|---------|-----------------|
| `ScenEdit_GetUnit` raises an error if unit not found | Wrap in `pcall` or check return value |
| Using unit names across sides | Use GUIDs — names are not unique |
| `VP_GetSide().units` may be empty | Check `#side.units > 0` before iterating |
| `ScenEdit_SetMission` with `patrolzone` overwrites the entire zone | Always supply all RPs in the array |
| Timed triggers fire at scenario time, not real time | Use `ScenEdit_CurrentTime() + offset` |
| `loadoutid` missing for aircraft | Spawns with no weapons; always specify |
| KeyStore value is a string | Always `tonumber()` when expecting a number |
| Contact GUID used where unit GUID expected | Use `contact.actualunitid` |
| Event script tries to use module-level variable | Use KeyStore; event scripts are sandboxed |

---

## Style Guide

- Use `local` for all variables inside functions
- Name constants in UPPER_SNAKE_CASE: `local MAX_UNITS = 10`
- Use EmmyLua/LuaLS annotations: `--- @param name type description`
- Nil-check all unit/side/mission lookups before use
- Store GUIDs in KeyStore immediately after `ScenEdit_AddUnit`
- Group related code with `-- ===` section comments
- Use `ScenEdit_SpecialMessage` for player-visible feedback, `print` for debug only
- Prefix event handler functions with `on_`: `local function on_carrier_destroyed()`

---

## References

- **API Docs:** https://commandlua.github.io
- **Wrappers reference:** https://commandlua.github.io/assets/Wrappers.html
- **Functions reference:** https://commandlua.github.io/assets/Functions.html
- **Enumerations:** https://commandlua.github.io/assets/Enumerations.html
- **Community forum (Lua Legion):** https://www.matrixgames.com/forums/tt.asp?forumid=1681
- **CMO Intellisense (blu3ser):** https://github.com/blu3ser/CMO_Intellisense
