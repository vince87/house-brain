"""Server-owned messages for this language."""

MESSAGES = {
    "authorization_invalid": "计划被拒绝，因为授权码缺失、格式错误或不正确；未模拟或执行任何操作。",
    "web_search_unavailable": "此 House Brain 实例未配置网络搜索。",
    "entity_ambiguous": "请求的名称无法唯一标识一个可控制实体。请指定设备的准确名称。",
    "entity_not_found": "未找到与请求名称匹配的实体。请检查设备名称。",
    "entity_not_controllable": "请求的实体存在，但未包含在可控制实体中。",
    "authorization_not_validated": "计划被拒绝，因为提供的代码未通过操作工具验证；未模拟或执行任何操作。",
    "action_not_validated": "无法完成命令，因为没有操作工具验证该命令；未模拟或执行任何操作。",
}

REJECTION_REASONS = {
    "authorization_code": "授权码缺失、格式错误或不正确",
    "kill_switch": "安全开关已禁用实际执行",
    "mode": "请求的模式未获授权",
    "explicit_entity": "建议的实体与请求的实体 ID 不匹配",
    "unresolved": "服务器未解析设备名称",
    "no_target": "搜索未找到唯一的可控制实体",
    "resolved_entity": "建议的实体与服务器解析结果不匹配",
    "not_included": "请求的实体 ID 不可控制",
    "action": "请求的操作未获策略授权",
    "value": "请求的值未获策略授权",
    "parameter": "请求的参数未获策略授权",
    "invalid": "生成的命令无效",
    "policy": "服务器策略拒绝了该计划",
}

REJECTION_PREFIX = "计划被拒绝，因为"
REJECTION_SUFFIX = "；未模拟或执行任何操作。"
