"""Render a standalone manual-template Lua with Score Spec v2 instrumentation."""

from __future__ import annotations

_V1_SCORE_MARKER = "-- score_spec_checksum:"
_ACTIVE_ATTACKS_MARKER = "-- SCHEDULE ACTIVE ATTACKS"
_PROCESS_SNAPSHOT_MARKER = "function baseline_process_snapshot(tag)\n"

_V2_SCORE_BLOCK = r'''
-- score_spec_version: 2.0.0
-- Mission score is cumulative ship damage. Process telemetry remains diagnostic.
local V2_SCORE_UNITS = {
    {unit_id='blue_cvn70', total=200, partial=true},
    {unit_id='blue_cg59', total=100, partial=true},
    {unit_id='blue_ddg113_1', total=75, partial=true},
    {unit_id='blue_ddg113_2', total=75, partial=true},
    {unit_id='red_liaoning', total=-200, partial=true},
    {unit_id='red_055_nanchang', total=-100, partial=true},
    {unit_id='red_052d_1', total=-75, partial=true},
    {unit_id='red_052d_2', total=-75, partial=true},
    {unit_id='red_j15_1', total=-20, partial=false},
    {unit_id='red_j15_2', total=-20, partial=false},
}

local function baseline_v2_score_key(unit_id)
    return 'baseline_v2_score/' .. tostring(unit_id)
end

local function baseline_v2_cumulative_award(rule, damage)
    if not rule.partial then return 0, 0 end
    local percent = math.max(0, math.min(100, tonumber(damage) or 0))
    local thresholds = {25, 50, 75, 100}
    local award = 0
    local reached_threshold = 0
    for _, threshold in ipairs(thresholds) do
        if percent >= threshold then
            award = math.floor((math.abs(rule.total) * threshold / 100) + 0.5)
            reached_threshold = threshold
        end
    end
    if rule.total < 0 then award = -award end
    return award, reached_threshold
end

local function baseline_v2_apply(rule, desired_award, threshold, reason)
    local key = baseline_v2_score_key(rule.unit_id)
    local prior_award = tonumber(ScenEdit_GetKeyValue(key) or '0') or 0
    local delta = desired_award - prior_award
    if delta == 0 then return end

    local ok, current = pcall(ScenEdit_GetScore, SIDE_RED)
    if not ok or type(current) ~= 'number' then
        print('[CMO-V2-SCORE] score_read_failed unit_id=' .. rule.unit_id)
        return
    end
    local description = string.format(
        'v2 mission score unit=%s threshold=%s delta=%d cumulative=%d reason=%s',
        rule.unit_id, tostring(threshold), delta, desired_award, tostring(reason)
    )
    local applied = pcall(ScenEdit_SetScore, SIDE_RED, current + delta, description)
    if not applied then
        print('[CMO-V2-SCORE] score_write_failed unit_id=' .. rule.unit_id)
        return
    end
    ScenEdit_SetKeyValue(key, tostring(desired_award))
    emit_json('[CMO-V2-SCORE]', {
        rule_id='mission_score/' .. rule.unit_id,
        unit_id=rule.unit_id,
        damage_threshold_percent=threshold,
        delta=delta,
        cumulative_unit_award=desired_award,
        score_after=current + delta,
        reason=reason,
    }, {'rule_id','unit_id','damage_threshold_percent','delta','cumulative_unit_award','score_after','reason'})
    emit_agent_event('SCORE_CHANGE', {
        rule_id='mission_score/' .. rule.unit_id,
        unit_id=rule.unit_id,
        damage_threshold_percent=threshold,
        delta=delta,
        score_after=current + delta,
        reason=reason,
    }, {'rule_id','unit_id','damage_threshold_percent','delta','score_after','reason'})
end

function baseline_v2_score_once()
    for _, rule in ipairs(V2_SCORE_UNITS) do
        local unit = unit_by_id(rule.unit_id)
        if rule.partial then
            if unit then
                local desired, threshold = baseline_v2_cumulative_award(rule, damage_percent(unit))
                if desired ~= 0 then
                    baseline_v2_apply(rule, desired, threshold, 'damage_threshold')
                end
            else
                baseline_v2_apply(rule, rule.total, 100, 'destroyed_missing_from_wrapper')
            end
        elseif not unit or unit.IsDestroyed then
            baseline_v2_apply(rule, rule.total, 100, 'destroyed_unit_poll')
        end
    end
end

local baseline_v2_poll_sequence = 0
function baseline_v2_score_poll()
    baseline_v2_score_once()
    baseline_v2_poll_sequence = baseline_v2_poll_sequence + 1
    schedule_lua(
        'baseline_v2_score_poll_' .. tostring(baseline_v2_poll_sequence),
        'baseline_v2_score_poll()',
        5
    )
end

schedule_lua('baseline_v2_score_poll', 'baseline_v2_score_poll()', 5)
print('[CMO-V2-SCORE] installed cumulative damage scoring rules=' .. tostring(#V2_SCORE_UNITS))
'''.lstrip()


def build_v2_score_baseline(source: str) -> str:
    """Replace legacy scoring while preserving the rendered attack scheduler tail."""
    if _V1_SCORE_MARKER not in source:
        raise ValueError("manual baseline does not contain a replaceable v1 score section")
    prefix, _, legacy_score_and_tail = source.partition(_V1_SCORE_MARKER)
    if _ACTIVE_ATTACKS_MARKER not in legacy_score_and_tail:
        raise ValueError("manual baseline does not contain the active attack scheduler tail")
    if _PROCESS_SNAPSHOT_MARKER not in prefix:
        raise ValueError("manual baseline does not contain the process snapshot hook")
    _, _, scheduler_tail = legacy_score_and_tail.partition(_ACTIVE_ATTACKS_MARKER)
    prefix = prefix.replace(
        _PROCESS_SNAPSHOT_MARKER,
        _PROCESS_SNAPSHOT_MARKER + "    baseline_v2_score_once()\n",
        1,
    )
    return (
        prefix.rstrip()
        + "\n\n"
        + _V2_SCORE_BLOCK
        + "\n-- ============================================================\n"
        + _ACTIVE_ATTACKS_MARKER
        + scheduler_tail
    )
