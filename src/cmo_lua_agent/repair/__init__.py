"""历史 Lua Repair 目录的包边界。

当前正式自动修复入口是 ``training.CodeRepairCoordinator`` 与 ``agents.SystemRepairAgent``；
本目录保留给旧接口和未来受控 Lua 修复演进，不能并行创建第二个 Training 修复循环。
"""
