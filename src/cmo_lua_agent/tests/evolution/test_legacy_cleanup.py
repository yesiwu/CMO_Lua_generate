from __future__ import annotations

import importlib

import pytest


def test_replaced_campaign_orchestrator_module_is_not_importable() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("cmo_lua_agent.evolution.campaign_orchestrator")
