from __future__ import annotations

def test_generation_one_profile_has_four_bounded_air_tactics_roles():
    # The profile is intentionally data-only so a preview can freeze it without an LLM call.
    from cmo_lua_agent.evolution.generation_experiment_profile import GenerationExperimentProfileBuilder
    profile = GenerationExperimentProfileBuilder().build(generation_index=1)
    roles = profile.roles
    assert set(roles) == {"candidate_00", "candidate_01", "candidate_02", "candidate_03"}
    assert roles["candidate_00"]["allowed_capabilities"] == ["air_tactics.ingress_altitude_m"]
    assert roles["candidate_01"]["required_capabilities"] == ["air_tactics.popup_range_nm"]
    assert roles["candidate_02"]["allowed_capabilities"] == ["air_tactics.launch_delay_seconds"]
    assert roles["candidate_03"]["max_changed_capabilities"] == 2
