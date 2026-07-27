# 褰撳墠瀹炵幇鐘舵€?
> 鐩樼偣鏃ユ湡锛?026-07-22銆傛湰鏂囧彧璁板綍宸叉帴鍏ャ€佸彲楠岃瘉鐨勪唬鐮佽矾寰勶紱瑙勫垝鏂囦欢鍜屾湭鎺ュ叆妯″潡涓嶇瓑鍚屼簬鍙敤鍔熻兘銆?
## 1. 褰撳墠涓婚摼璺?
椤圭洰褰撳墠鏈変袱鏉″彲鐢ㄤ絾灏氭湭闂幆鐨勭‘瀹氭€ч摼璺細

```text
Chat / run CLI
  -> ScenarioWorkflow
  -> JsonLoader -> Schema / Semantic -> IR -> DatabaseResolver
  -> ScenarioDefinition + InitialStrategyHint
  -> ManifestBuilder -> CMOLua-main -> Preflight -> original.lua

execute_cmo Tool
  -> CmoRunner -> CmoJobConfig + CmoProcessRunner
  -> BatchRunner runner.log / cmo_output.txt / result.json
```

`ScenarioWorkflow` 鍦?Lua 鐢熸垚鎴愬姛鍚庣粨鏉燂紝涓嶄細鑷姩鎵ц CMO銆俙execute_cmo` 淇濇寔鐙珛銆佷汉宸ュ鎵圭殑宸ュ叿璋冪敤銆傚洜姝も€淟ua 宸茬敓鎴愨€濆拰鈥淐MO 鎺ㄦ紨鎴愬姛鈥濅粛鏄袱浠剁嫭绔嬬殑浜嬶紝鎵ц缁撴灉灏氭湭鍥炴祦涓虹粺涓€鎴樻灉銆佽瘎鍒嗘垨鍊欓€夌粨鏋溿€?
## 2. 宸插疄鐜版ā鍧?
| 鍖哄煙 | 鐘舵€?| 璇存槑 |
| --- | --- | --- |
| `ingest` / `contract` | 宸插疄鐜?| JSON 璇诲彇銆佺粨鏋?璇箟鏍￠獙銆両R銆佹暟鎹簱瑙ｆ瀽銆丮anifest 鏋勫缓銆傚钩鍙版涔夎繑鍥?`NEEDS_USER_INPUT`銆?|
| Phase 1 绛栫暐濂戠害 | 宸插疄鐜?| `ScenarioDefinition` 淇濆瓨鍗曚綅銆丏BID銆佸熀鍦般€丩oadout 涓庢鍣ㄦ渶澶у簱瀛橈紱`InitialStrategyHint` 淇濆瓨鏃?JSON 鐨勮鍒掞紱`StrategySpec` 鏄敮涓€姝ｅ紡绛栫暐琛ㄨ揪銆?|
| Phase 1 Baseline | 宸插疄鐜?| `baseline/6v4/baseline_strategy.json` 鏄汉宸ョ淮鎶ょ殑宸查獙璇佸熀绾匡紝鍖呰鍚屼竴涓?`StrategySpec` 鍜屾潵婧愬厓鏁版嵁锛涗笉鍋?Lua 鍙嶅悜瑙ｆ瀽銆?|
| `generation` | 宸插疄鐜?| 鏃ч摼璺腑鐨?`LuaGenerationService` 缁х画璋冪敤 `CMOLua-main`锛汸hase 2 骞惰澧炲姞 `ExecutionPlanCompiler`銆乣CapabilityValidator`銆乣LuaRuntimeProfile`銆佸垎灞?Runtime Primitive/Helper銆佺‘瀹氭€?`LuaRenderer` 鍜?`Phase2GoldenBaselineService`銆?|
| Phase 3.1 鍘熺敓璁″垎 | 宸插疄鐜颁絾鏈帴鍏ユ覆鏌?| `UnitRoleCatalog`銆乣ScoreProfile`銆乣ScenarioObjectives`銆乣ScenarioScoreSpec` 涓?`CmoNativeScoreCompiler` 鍙‘瀹氭€х敓鎴?CMO `UnitDestroyed 鈫?Points 鈫?Event` 鐗囨銆傝瘎鍒嗙墖娈垫槸绯荤粺绾?instrumentation锛屽皻鏈彃鍏?Renderer锛屼篃鏈墽琛?CMO 鎴栬В鏋愮粨鏋溿€?|
| `execution` | 宸插疄鐜?| `CmoRunner`銆乣CmoProcessRunner`銆佽繘搴﹁В鏋愩€佽秴鏃躲€佹壒娆℃眹鎬汇€佺粨鏋滀繚瀛樺潎鍦ㄦ寮忛摼璺腑銆傛棤寮曠敤涓旇娉曟棤鏁堢殑 `cmo_executor.py` 宸茬Щ闄ゃ€?|
| `tools` / `cli` | 宸插疄鐜?| Chat 鏀寔鏂囦欢銆丼kill銆佹暟鎹簱銆丣SON鈫扡ua 鍜?CMO 宸ュ叿锛汻ich 缁堢鏀寔娴佸紡鏂囨湰銆佸鎵瑰拰宸ュ叿杩涘害銆?|
| `artifacts` | 宸插疄鐜?| 姣忔 JSON鈫扡ua Workflow 淇濆瓨杈撳叆銆佹牎楠屻€両R銆丮anifest銆丩ua 鍙?Phase 1 娲剧敓浜х墿锛汸hase 2 Golden 鍙︿繚瀛?plan銆乺enderer manifest銆乻ource map 鍜?Golden Manifest銆?|

## 3. Phase 1 鏁版嵁杈圭晫

```text
鏃?JSON
  -> ScenarioIR锛堝吋瀹规棫閾捐矾锛屼粛鍚?strikePlan锛?  -> ScenarioDefinition锛堜粎浜嬪疄锛?  -> InitialStrategyHint锛堟棫 JSON 涓殑鍒濆璁″垝锛?
鏄惧紡 baseline_path
  -> BaselineStrategy锛堝凡楠岃瘉 StrategySpec锛?  -> initial_hint_vs_baseline.json
```

`weaponLoad` 鐨勮竟鐣屽浐瀹氬涓嬶細姝﹀櫒鍚嶇О銆丏BID 涓庢渶澶у簱瀛樿繘鍏?`ScenarioDefinition`锛涙湰娆′娇鐢ㄦ鍣ㄣ€佸彂灏勯噺銆佺洰鏍囧垎閰嶃€佸欢杩熴€佽埅璺拰淇濈暀閲忚繘鍏?`StrategySpec`銆俙StrategyValidator` 鐨勬寮忓叕寮€杈撳叆鏄?`StrategySpec + ScenarioDefinition`锛屼笉渚濊禆鏃?`ScenarioContract`銆?
鏅€氱敓浜?JSON 鍙繚瀛橈細

```text
contract/scenario_definition.json
strategy/initial_strategy_hint.json
validation/strategy_report.json
```

鍙湁鏄惧紡閰嶇疆涓?`scenario_id` 鍖归厤鐨勫凡楠岃瘉 Baseline 鎵嶄繚瀛橈細

```text
strategy/baseline_strategy.json
strategy/initial_hint_vs_baseline.json
```

## 4. Phase 2 纭畾鎬?Golden 閾捐矾

```text
ScenarioDefinition + StrategySpec
  -> ExecutionPlanCompiler
  -> ExecutionPlan
  -> CapabilityValidator
  -> LuaRuntimeProfile + registered Plan Primitives
  -> deterministic LuaRenderer
  -> rendered_baseline.lua
```

褰撳墠鍙鐩栧凡楠岃瘉鐨?6v4 娴风┖鍗忓悓鍙嶈埌 Baseline锛屼綔涓哄苟琛岄獙璇佸叆鍙ｏ紝涓嶆浛鎹?Chat 榛樿鐢熸垚璺緞銆乣ScenarioWorkflow`銆乣generate_cmo_lua` 鎴?Auto 妯″紡銆俁untime Helper锛堜緥濡?`lookup_unit`銆乣schedule_lua`銆乣checked_cmo_call`锛夊彧鍦?Primitive 鍐呴儴浣跨敤锛屼笉浼氭垚涓虹嫭绔?Operation銆侴olden Manifest 璁板綍杈撳叆銆佽繍琛屾椂銆佺紪璇戝櫒/娓叉煋鍣ㄧ増鏈€乧hecksum銆丆MO 缁撴灉鐩綍鍜岄獙璇佺姸鎬侊紱CMO 鐗堟湰鏈粠杩愯浜х墿鍙潬鍙栧緱鏃舵爣璁颁负 unavailable/unknown銆?
## 5. Agent銆乄orkflow 涓庡皻鏈疄鐜板璞?
宸叉帴鍏ワ細`AgentLoop`銆乣ScenarioWorkflow`銆乣CmoRunner`銆乣ScenarioInput`銆乣ScenarioIR`銆乣ScenarioContract`銆乣ResolvedScenarioManifest`銆丳hase 1 绛栫暐妯″瀷銆?
鏂囦欢瀛樺湪浣嗘湭杩涘叆鐢熶骇涓婚摼璺細`agents/strategy_proposal_agent.py`銆乣lua_synthesis_agent.py`銆乣lua_repair_agent.py`銆乣comparative_learning_agent.py`銆乣skill_author_agent.py`锛屼互鍙婃棫 `generation/strategy_generator.py` / `candidate_generator.py`銆?
灏氭湭瀹炵幇锛歅hase 3.2 鐨勮瘎鍒嗙墖娈?Renderer 鎺ュ叆銆乣RuntimeTelemetry`銆乣CmoNativeSnapshot`銆乣ResultArtifactPaths`銆乣CombatEvidenceBundle`銆乣EvidenceReconciler`銆佹寮忛棴鐜?`SemanticValidator`銆乣CombatMetrics`銆乣CombatScorer`銆乣CandidateOutcome` 鍜?`CandidateEvaluationWorkflow`銆侰MO 鍘熺敓璁″垎缁撴灉灏氭湭缁忚繃鐪熷疄鎵ц鎴栫粨鏋滆В鏋愶紱椤圭洰涓嶅绉板凡鍏峰鎴樻灉璇勫垎銆佸€欓€変紭鍖栨垨缁忛獙杩涘寲銆?
## 6. ToolRegistry 涓庢潈闄?
鍞竴鐢熶骇娉ㄥ唽鍏ュ彛鏄細

```text
src/cmo_lua_agent/tools/tool_base/factory.py
-> build_tool_registry(...)
```

`execute_cmo`銆乣create_file`銆乣create_json_copy`銆乣edit_file` 闇€瑕佸鎵癸紱鏂囦欢銆佺洰褰曘€丼kill 涓庡彈闄愭暟鎹簱鏌ヨ涓哄彧璇诲伐鍏凤紝涓嶉渶瑕佸鎵广€傛寮?Skill 璺緞鏄?`list_skills -> load_skill`锛涙棫 CMO 涓撶敤璇诲彇/鎼滅储宸ュ叿淇濈暀妯″潡涓庢祴璇曪紝浣嗕笉浣滀负姝ｅ紡鍏ュ彛娉ㄥ唽銆?
## 7. 閲嶅鍜屾棫璺緞

- `CMOLua-main/tools/json_to_lua.py` 浠嶅惈鑷韩 JSON 瑙ｉ噴銆佹鍣ㄥ厹搴曞拰 Lua 妯℃澘閫昏緫锛屼笌 `contract` / `generation` 灞€閮ㄩ噸鍙狅紱瀹冪洰鍓嶆槸绋冲畾鐢熸垚鍣ㄦ潵婧愶紝涓嶅簲鍒犻櫎銆?- 褰撳墠鍏煎 JSON 鐨?`weaponLoad`銆乣strikePlan` 娣峰悎浜嬪疄涓庣瓥鐣ワ紱Phase 1 浠ュ苟琛屾淳鐢熶骇鐗╅殧绂讳簩鑰咃紝鏈敼鍙樻棫杈撳叆鏍煎紡銆?- `ScenarioWorkflow` 椤堕儴鍘嗗彶璇存槑浠嶆弿杩板畬鏁存墽琛?淇娴佺▼锛屼絾瀹為檯浠ｇ爜鍙繍琛屽埌 Lua 鐢熸垚锛涘悗缁紩鍏ュ€欓€夎瘎浼板伐浣滄祦鏃跺簲涓€骞舵竻鐞嗚鏃ф枃妗堛€?
## 8. 娴嬭瘯涓庡仴搴锋鏌?
鏍圭洰褰?`pytest.ini` 鍥哄畾锛?
```ini
testpaths = src/cmo_lua_agent/tests
pythonpath = src
addopts = --import-mode=importlib
```

杩欒В鍐充簡鍚屽悕娴嬭瘯妯″潡鐨勬敹闆嗗啿绐侊紝骞跺皢鏃ч《灞傚鍏ヤ慨姝ｄ负绋冲畾鍖呰矾寰勩€?
2026-07-23 Phase 3.1 楠岃瘉缁撴灉锛?
```text
鍏ㄩ噺娴嬭瘯锛?61 passed, 2 skipped锛坧ytest cache 鏉冮檺璀﹀憡涓嶅奖鍝嶇粨鏋滐級銆?```

`compileall` 鏇惧彂鐜版棤寮曠敤鐨?`execution/cmo_executor.py` 璇硶鏃犳晥锛涜鏂囦欢宸插垹闄ゃ€備笅涓€娆″仴搴锋鏌ュ簲浣跨敤锛?
```powershell
python -m compileall src\cmo_lua_agent
python -m pytest src\cmo_lua_agent\tests -q
```

## 9. 褰撳墠缁撹

椤圭洰宸插叿澶囩ǔ瀹氱殑 JSON鈫扡ua 涓庡崟 Lua鈫扖MO 鎵ц鑳藉姏锛屽凡瀹屾垚 Phase 1 鍦烘櫙浜嬪疄/绛栫暐鍒嗙銆丳hase 2 6v4 纭畾鎬?Golden锛屼互鍙婂畬鏁?Phase 3 鐨?CMO 鍘熺敓璁″垎涓庢渶灏忔墽琛屽弽棣堥棴鐜€傚綋鍓嶅彲瀵?scored 6v4 鑷姩瀹氫綅鏈疆 Results銆佹牳楠屽師鐢熷垎鏁板苟鐢熸垚鍙璁＄殑璇勫垎浜х墿锛涘皻鏈叿澶?Candidate 姣旇緝銆丷esearch Reward銆佽嚜鍔ㄤ慨澶嶆垨浼樺寲闂幆鑳藉姏銆?
## 10. Phase 3.2 鍘熺敓璁″垎缁勮

宸插疄鐜板苟琛岀殑 scored Golden 閾捐矾锛屼笖涓嶆敼鍙?Chat 榛樿鐢熸垚璺緞鎴?Phase 2 Golden锛?
```text
ScenarioDefinition + StrategySpec -> ExecutionPlanCompiler
ScenarioDefinition + UnitRoleCatalog + ScoreProfile + ScenarioObjectives
  -> CmoNativeScoreCompiler
ExecutionPlan + LuaRuntimeProfile + NativeScoreCompilation
  -> ScoredLuaAssemblyService -> LuaRenderer
  -> baseline/6v4/scored/rendered_scored_baseline.lua
```

`SystemInstrumentationBundle` 鍙帴鍙楃郴缁熺敓鎴愮殑 `NativeScoreCompilation`锛屽苟鏍￠獙鍦烘櫙銆佽瘎鍒嗗绾︺€佺墖娈点€丷untime 鍜?Renderer 鐗堟湰銆傝瘎鍒嗙墖娈靛浐瀹氭彃鍏ュ湪鍗曚綅涓庤埌杞芥満閰嶇疆涔嬪悗銆佺涓€鏉℃敾鍑讳箣鍓嶏紱瀹冧笉鏄?ExecutionPlan Operation銆俿cored Runtime 浣跨敤 `cmo_naval_air_anti_surface_scored@2.0.0`锛屼絾浠嶅鐢ㄥ敮涓€鐨?Runtime Helper 涓?`LuaRenderer` 瀹炵幇銆?
2026-07-23 鐨勭湡瀹?CMO Golden run 涓?`phase32_scored_6v4_cdrive_2`锛岀粨鏋滅洰褰?`C:\CMO\CmoBatchRunner\Results\20260723-102542`锛欱atch 鎴愬姛 1銆佸け璐?0锛涘崄鏉?CMO 鍘熺敓璁″垎瑙勫垯鍧囧畬鎴愭敞鍐岋紱涓ゆ灦 J-15 琚瘉鍚庣孩鏂瑰師鐢熷垎鏁颁负 `-40`锛屼笌 `carrier_fighter` 鐨勬瘡鏋?`-20` 瑙勫垯涓€鑷淬€傝淇℃伅鍙綔涓?Golden 瀹¤璁板綍锛涢」鐩粛鏈疄鐜?Results 鐩綍瀹氫綅銆丼QLite/CSV 瑙ｆ瀽銆丒videnceReconciler銆丆ombatMetrics 鎴?Research Reward銆?
## 12. Phase 4 鍙楁帶 Agent

Phase 4 宸插疄鐜颁袱涓湭鎺ュ叆 Chat 鎴?Auto 榛樿璺緞鐨勫彈鎺?Agent锛?
```text
LuaSynthesisAgent
  CREATE: StructuredStrategyClient -> 瀹屾暣 StrategySpec
  REVISE: StructuredStrategyClient -> RestrictedStrategyPatch
  -> StrategyChangeGuard -> StrategyValidator
  -> ExecutionPlanCompiler -> CapabilityValidator
  -> LuaRenderer / ScoredLuaAssemblyService -> ArtifactWriter

LuaRepairAgent
  Structured CmoError -> RepairErrorRouter
  -> StrategyPatch | RuntimePatchProposal | RuntimeDefectReport
```

`LuaSynthesisAgent` 涓嶇敓鎴愯嚜鐢?Lua锛屼篃涓嶆墽琛?CMO銆侰REATE 妯″紡鍙帴鏀跺畬鏁翠弗鏍肩殑 `StrategySpec`锛汻EVISE 妯″紡浠呮敮鎸佺幇鏈夊彾瀛愬瓧娈电殑 `replace`锛屾暟缁勯」蹇呴』浠?`attack_id` 鎴?`sortie_id` 鏍搁獙銆俙StrategyChangeGuard` 浼氭嫆缁濇湭鎺堟潈璺緞銆佺鍏?鍚庝唬璺緞銆佸瓧娈电己澶便€佹暟缁勯噸鎺掑拰绋冲畾 ID 涓嶅尮閰嶏紝骞惰緭鍑虹郴缁熼獙璇佺殑 `verified_changed_paths`銆侺ua 涓?manifest 鍦ㄥ叏閮ㄦ牎楠屻€佺紪璇戝拰娓叉煋鎴愬姛鍚庢墠鐢?`ArtifactWriter` 鍘熷瓙鍐欏叆锛涙枃浠惰韩浠藉寘鍚満鏅€佺瓥鐣ャ€丷untime銆丷enderer銆佽瘎鍒嗙墖娈靛拰 Compiler 鐨勭ǔ瀹?checksum銆?
`LuaRepairAgent` 姣忔鏈€澶氳皟鐢ㄤ竴娆＄粨鏋勫寲 JSON 瀹㈡埛绔紝涓嶆墽琛屻€佷笉閲嶈瘯銆佷笉淇敼鍦烘櫙浜嬪疄鎴?CMO 鍘熺敓璁″垎銆俙RepairErrorRouter` 鍐冲畾 `retry_eligible`锛屾ā鍨嬭嚜鎶ョ殑 `agent_confidence` 浠呯敤浜庡睍绀恒€俙RuntimePatchProposal` 涓嶅惈 Lua 鏂囨湰锛屽繀椤荤粡 `RuntimePatchRegistry` 楠岃瘉宸叉敞鍐岀被鍨嬨€丱peration銆丷untime 鍏煎鎬у拰璇勫垎鍖哄煙闅旂锛涙湭娉ㄥ唽鎴栦笉閫傜敤鐨勬彁妗堜細杞负 `RuntimeDefectReport`銆侾hase 4 灏氭湭瀹炵幇鎵ц寰幆銆佷慨澶嶉绠椼€丆MO 鑷姩閲嶈窇銆佸€欓€夋瘮杈冦€佹帓琛屾銆佺粡楠岀郴缁熸垨 Chat/Auto 榛樿璺緞鎺ュ叆銆?
## 13. Phase 5 鍗曞€欓€夎瘎浼?
`CandidateEvaluationWorkflow` 宸叉彁渚涘崟涓?scored 鍊欓€夌殑绛栫暐鏍￠獙銆佽鍒掔紪璇戙€佺‘瀹氭€?Lua 娓叉煋銆丆MO 璋冪敤銆丳hase 3 鐩存帴璇勪及鍜岀粺涓€ `CandidateOutcome` 钀界洏銆傚畠鏀寔鍙楅檺 `StrategyPatch`锛屼互鍙婂敮涓€宸叉敞鍐岀殑 Runtime Patch `retry_missing_contact_once`锛氳琛ヤ竵鍙鍒跺苟鏇存柊 `prepare_target_contact` Operation锛屼笉淇敼 Strategy銆佽瘎鍒嗙墖娈垫垨鍘?Plan銆俙Phase3RepairSignalMapper` 浠呮秷璐?Phase 3 宸茶В鏋愮殑缁撴瀯鍖栨敾鍑昏瘉鎹紝灏?`missing_contact` 鍥炴祦鍒板彈鎺?Runtime Patch锛涙湭鏀寔鐨勫姩鎬侀敊璇笉浼氭墿灞曚负鑷敱 Lua 淇銆?
Phase 5 浠嶄笉鐢熸垚鍥涘€欓€夈€佷笉鎻愪緵 CandidateComparator/鎺掕姒滐紝涔熸湭鎺ュ叆 Chat銆丄uto銆丒xperience 鎴?Skill銆傚綋鍓嶆櫘閫氬洖褰掍负 `491 passed, 2 skipped`锛涚湡瀹?scored 6v4 Candidate Workflow CMO 楠屾敹灏氶渶鍦ㄥ叿澶囪冻澶熸墽琛岀獥鍙ｆ椂鍗曠嫭杩愯骞惰褰?run_id銆丷esults 涓?Outcome銆?
## 14. Phase 6 鍙楅檺鍥涘€欓€変紭鍖?
Phase 6 鏂板鐙珛鐨?`OptimizationGenerationWorkflow`锛屼絾娌℃湁鎺ュ叆 Chat 鎴?Auto銆?瀹冧粠椤圭洰鍐呭彧璇荤殑浜哄伐 Bootstrap Skill
`src/cmo_lua_agent/skills/bootstrap/cmo_naval_air_strategy_proposal_v1.md`
鍒涘缓鍐荤粨蹇収锛屽啀鐢卞敮涓€姝ｅ紡瀹炵幇
`optimization.strategy_proposal_agent.StrategyProposalAgent` 鎻愬嚭鍥哄畾鍥涗釜瀹屾暣
`StrategySpec`銆傛棫鐨勬湭璺熻釜 `agents/strategy_proposal_agent.py` 涓嶅湪杩愯鏃跺鍏ュ浘涓€?
鍊欓€夊湪鎵ц鍓嶅繀椤婚€氳繃 `CandidateSetValidator`锛氬彧鑳戒慨鏀?Baseline 宸叉湁绋冲畾 ID
瀵硅薄鐨勫厑璁稿彾瀛愬瓧娈碉紝涓嶅緱鏂板銆佸垹闄ゃ€侀噸鎺掓垨淇敼鏀诲嚮/鍑哄姩 ID锛涚瓥鐣ャ€佸簱瀛樸€?宸紓鍜岀粍鍐呭鏍锋€у潎鐢辩‘瀹氭€т唬鐮侀獙璇併€傚伐浣滄祦鎺掍粬鍒涘缓浼樺寲鐩綍骞惰褰?`in_progress`銆乣completed` 鎴?`failed` Manifest锛岄殢鍚庝覆琛岃皟鐢?Phase 5 璇勪及 Baseline
鍜屽洓涓€欓€夈€俙CandidateComparator` 浠呮瘮杈冭瘎鍒嗗绾︿竴鑷寸殑 Outcome锛屾寜鎵ц澶辫触銆?璇箟鏃犳晥銆佷笉鍙瘎鍒嗐€佸彲鎺掑悕鎴愬姛鍒嗙被锛屽苟浠呭鍙帓鍚嶇粨鏋滀娇鐢?CMO 鍘熺敓鍒嗘暟鎺掑簭銆?
鏈樁娈典粛鏈疄鐜?Skill 鎼滅储/婵€娲?缂栬緫銆佺粡楠屽涔犮€佸浠ｅ€欓€夈€佸苟琛?CMO銆丆hat/Auto
鎺ュ叆鎴?Research Reward銆侾hase 6 鐨勭湡瀹?CMO 闆嗘垚楠屾敹灏氶渶浣跨敤鍥哄畾鍥涘€欓€?fixture
杩愯浜旀涓茶 CandidateEvaluationWorkflow锛涙櫘閫氬崟鍏冨拰鍥炲綊娴嬭瘯涓嶄緷璧栫湡瀹?CMO銆?
## Phase 6 Official Score Source (2026-07-25)

Phase 3 now treats `execution-summary.json#/official_score/final` as the
sole authority for a formal CMO native score. SQLite, CSV, loss records and
the minimum intermediate score are evidence only; none can replace the final
official total. The parser validates the ordered score-event chain and its
delta against `official_score.initial/final`.

The formal CandidateOutcome persists execution success, native score,
scoreability, semantic validity, rank and the score-source pointer. A semantic
failure retains the verified native score but is excluded from ranking.

The five formal runs under `runs/phase6_score_summary_20260725_b` emit
execution summaries through the BatchRunner audit profile. Their official
totals are all `0` because no score event fired in those formal rendered runs;
this is a runtime/strategy outcome, not a score-parser fallback. The historical
candidate_03 summary independently parses as `0 -> -20 -> -40 -> 35`.

## 11. Phase 3 鏈€灏忔墽琛屽弽棣堥棴鐜?

宸插疄鐜?`Phase3EvaluationService` 涓?`Phase3EvaluationHook` 鐨勬渶灏忛棴鐜€俿cored 鎵ц鍙皢 Hook 浜ょ粰 `CmoRunner`锛屽湪 `CmoRunResult` 鍜岃繍琛屼骇鐗╄惤鐩樺悗鑷姩璇勪及锛屼笖 Hook 澶辫触鍙啓鍏?`unscorable` 浜х墿锛屼笉鏀瑰彉鍘熷 CMO 鎵ц缁撹銆傜粨鏋滃畾浣嶅彧鎺ュ彈 `CmoRunResult` 鏄惧紡缁欏嚭鐨?`batch_result_dir`锛屼笉鎵弿鎴栭€夋嫨鍘嗗彶鏈€鏂?Results锛涗粎鍦ㄥ敮涓€ `001_*` job 鐨?`events.sqlite` 涓牳楠屾湰杞?Lua 鑴氭湰鍚嶏紝SQLite 涓嶅彲鐢ㄦ椂鎵嶈鍙栧悓 job 鐨?`combat-summary.csv`銆傝В鏋愬櫒鍙鍙?`side_scores`銆佸満鏅崟浣嶆瘉浼ゃ€佽鍒掔浉鍏?`weapon_events`銆乣run_info` 涓庢湰 job 鐨?`lua-output.log`锛屼笉浼氳В鏋愬畬鏁?AALog 鎴栦繚鐣欏師濮嬩簨浠舵祦銆?
浜х墿鍥哄畾涓?`combat_evidence.json`銆乣semantic_validation.json`銆乣combat_metrics.json` 鍜?`reward_breakdown.json`銆俙EvidenceReconciliation` 鍙緭鍑?`valid`銆乣unscorable`銆乣result_integrity_failed`锛涙湭鐭ュ満鏅崟浣嶃€佽剼鏈笉鍖归厤鎴栬瘎鍒嗚鍒欐瘉浼や笌 CMO 鍘熺敓鍒嗘暟涓嶄竴鑷存椂鎷掔粷璇勫垎銆侰MO 姝﹀櫒瀵硅薄鐨勮嚜姣佽褰曚笉浣滀负鍦烘櫙鍗曚綅姣佷激銆俙AttackEpisode` 浠呮潵鑷?ExecutionPlan 涓殑鏀诲嚮鎿嶄綔锛屽苟鍦ㄦ暟鎹彲寰楁椂鑱氬悎鍙戝皠銆佸懡涓拰鎷︽埅锛涙櫘閫氳疆璇㈠拰閲嶅鎴愬姛鏃ュ織涓嶄細杩涘叆 `key_events`銆?
鏈€鏂拌嚜鍔ㄧ鍒扮楠岃瘉涓?`phase3_gate_6v4_cdrive_5`锛孯esults 浣嶄簬 `C:\CMO\CmoBatchRunner\Results\20260723-152951`锛欱atch 鎴愬姛 1銆佸け璐?0锛屼换鍔￠厤缃仮澶嶆垚鍔燂紱绾㈡柟鍘熺敓鍒嗘暟宸负 `-40`锛宍red_j15_1` 涓?`red_j15_2` 鍚勭敓鎴愪竴涓?`-20` 姣佷激璁″垎椤癸紝鍥涗唤 JSON 鑷姩鍐欏叆 `runs/phase3_gate_6v4_cdrive_5/phase3/`銆傝繖涓嶆槸 Research Reward銆丆andidateOutcome 鎴?CandidateEvaluationWorkflow锛涘悗缁樁娈典粛椤讳繚鎸佽繖浜涜竟鐣屻€?
