import sys
sys.path.insert(0, '.')
from cmo_lua_agent.evolution.auto_campaign_tools import auto_campaign_tools
print('auto_campaign_tools names:', [t.name for t in auto_campaign_tools()])
print('all OK')
