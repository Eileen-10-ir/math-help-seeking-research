"""Generic high-tier local guidance; v7 classification and routing stay intact."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
for relative in ['数学交互与论文初稿20261009/code', '数学主线严谨重跑20260930/code']:
    folder = str(ROOT / relative)
    if folder not in sys.path:
        sys.path.append(folder)

from routing_v7 import support as previous_support, MEDIUM_SUFFIX

ROUTING_VERSION = 'conversation-support-v8-generic-edge-20261021'
HIGH_TEMPLATE_ID = 'generic_math_help_boundary_v1'
HIGH_REPLY = (
    '我们先从你想弄懂的一步开始，暂不直接给出整题答案。'
    '你可以告诉我已经想到的方法、写出的一步，或者指出不明白的概念。'
    '如果还没有思路，也可以直接说明你需要起步提示。'
)


def support(text, task_id, task, result, gateway, history):
    record = previous_support(text, task_id, task, result, gateway, history)
    record['routing_version'] = ROUTING_VERSION
    if record['route_requested'] == 'edge_fixed':
        assert record['external_cloud_attempts'] == 0
        record.update(
            text=HIGH_REPLY,
            tier='本地通用求助引导',
            fixed_template_id=HIGH_TEMPLATE_ID,
            fixed_template_source='versioned generic local guidance; no cloud generation',
            support_policy='generic_high_tier_help_boundary',
        )
    return record
