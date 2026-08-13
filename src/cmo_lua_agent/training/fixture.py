"""仅供旧版 CLI Fixture 模式使用的确定性无 CMO 驱动器。

它模拟 Campaign 生命周期以支持离线测试；生产训练必须使用真实 Campaign 驱动器，
因此此处不会生成 Lua、调用 CMO 或写入真实训练产物。
"""

from __future__ import annotations


class FixtureCampaignDriver:
    """满足 ``CampaignDriver`` 协议的测试替身，所有代均立即成功完成。"""

    def prepare(self, request):
        """返回与生产实现一致格式的虚拟 Campaign ID。"""
        return f"{request.workflow_id}-campaign"

    def preview(self, campaign_id: str, generation_index: int) -> None:
        """Fixture 不生成候选方案，因此预览为无副作用操作。"""

    def execute(self, campaign_id: str, generation_index: int) -> None:
        """Fixture 不调用 CMO，因此执行为无副作用操作。"""

    def inspect_generation(self, campaign_id: str, generation_index: int) -> dict[str, object]:
        """直接返回完成状态，使 Runner 可验证逐代状态转换。"""
        return {"status": "completed"}
    def pause(self, campaign_id: str) -> None:
        """保留协议形状；Fixture 没有后台 Worker 需要暂停。"""

    def resume(self, campaign_id: str) -> None:
        """保留协议形状；Fixture 没有后台 Worker 需要恢复。"""

    def stop(self, campaign_id: str) -> None:
        """保留协议形状；Fixture 不持有可停止的 CMO 进程。"""

    def reconcile(self, campaign_id: str) -> dict[str, object]:
        """返回完成状态，模拟生产 Campaign 的恢复对账结果。"""
        return {"status": "completed"}

    def run_phase8(self, campaign_id: str, completed_generations: tuple[int, ...]) -> dict[str, object]:
        """返回虚拟 Phase 8 任务 ID，不创建真实经验或 Skill 资产。"""
        return {"status": "completed", "phase8_run_id": f"{campaign_id.removesuffix('-campaign')}_phase8"}
