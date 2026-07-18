# AgentGuard DataFlow V2 原型图提示词

Use case: ui-mockup

Asset type: high-fidelity desktop web application prototype for a developer security infrastructure product.

Primary request: Create a polished 16:9 desktop dashboard for “AgentGuard DataFlow”, an MCP cross-tool data provenance and sensitive-data leakage prevention gateway. The main visual is an interactive data lineage graph rather than a generic analytics dashboard.

Layout: left navigation; top gateway status; four metric cards; large MCP data lineage graph; leakage blocking detail panel; transformation detection table; recent tool-call table.

Visible navigation: 流量总览、数据血缘、工具策略、攻击回放、基准评测。

Main lineage: Email MCP → 外部邮件 → Filesystem MCP → Secret 数据 → GitHub MCP. Show UNTRUSTED, sensitivity:secret and external_write labels, with the final write visibly blocked.

Blocking detail: DENY; 来源 /secrets/api_key.txt; 目标 github.create_issue; 数据匹配 96%; 变形方式 Base64 + 拼接; 命中策略 block_secret_to_external; 处理结果 写入已阻止.

Transformation checks: 原文匹配、子串匹配、Base64、拆分重组 all marked PASS.

Visual style: dark navy professional developer tooling UI, cyan trusted state, amber untrusted state, violet processing, red secret/leakage path, restrained visual effects, modern Chinese sans-serif typography.

Constraints: desktop product UI only; all panels visible; no people, photos, 3D objects, crypto imagery, excessive glow or watermark; Chinese text readable.

Generation mode: built-in image generation tool.
