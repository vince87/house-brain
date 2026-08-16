"""Server-owned messages for this language."""

MESSAGES = {
    "authorization_invalid": (
        "인증 코드가 없거나 형식이 잘못되었거나 올바르지 않"
        "아 계획이 거부되었습니다. 어떤 작업도 시뮬레이션되"
        "거나 실행되지 않았습니다."
    ),
    "web_search_unavailable": (
        "이 House Brain 인스턴스에는 웹 검색이 설정되어 있지 않습니다."
    ),
    "entity_ambiguous": (
        "요청한 이름이 제어 가능한 단일 엔터티를 식별하지 "
        "못합니다. 정확한 장치 이름을 지정하세요."
    ),
    "entity_not_found": (
        "요청한 이름과 일치하는 엔터티를 찾지 못했습니다. 장치 이름을 확인하세요."
    ),
    "entity_not_controllable": (
        "요청한 엔터티가 존재하지만 제어 가능한 엔터티에 포함되어 있지 않습니다."
    ),
    "authorization_not_validated": (
        "제공된 코드가 작업 도구에서 검증되지 않아 계획이 "
        "거부되었습니다. 어떤 작업도 시뮬레이션되거나 실행되"
        "지 않았습니다."
    ),
    "action_not_validated": (
        "작업 도구가 명령을 검증하지 않아 완료할 수 없습니"
        "다. 어떤 작업도 시뮬레이션되거나 실행되지 않았습니"
        "다."
    ),
}

REJECTION_REASONS = {
    "device_code": ("기기에 Home Assistant 코드가 필요합니다"),
    "service": ("생성된 서비스가 Home Assistant에 존재하지 않습니다"),
    "authorization_code": ("인증 코드가 없거나 형식이 잘못되었거나 올바르지 않습니다"),
    "kill_switch": ("안전 스위치가 실제 실행을 비활성화했습니다"),
    "mode": ("요청한 모드가 승인되지 않았습니다"),
    "explicit_entity": ("제안된 엔터티가 요청한 엔터티 ID와 일치하지 않습니다"),
    "unresolved": ("서버가 장치 이름을 해석하지 못했습니다"),
    "no_target": ("검색에서 제어 가능한 단일 엔터티를 찾지 못했습니다"),
    "resolved_entity": ("제안된 엔터티가 서버 해석 결과와 일치하지 않습니다"),
    "not_included": ("요청한 엔터티 ID는 제어할 수 없습니다"),
    "action": ("요청한 작업이 정책에서 승인되지 않았습니다"),
    "value": ("요청한 값이 정책에서 승인되지 않았습니다"),
    "parameter": ("요청한 매개변수가 정책에서 승인되지 않았습니다"),
    "invalid": ("생성된 명령이 유효하지 않습니다"),
    "policy": ("서버 정책이 계획을 거부했습니다"),
}

REJECTION_PREFIX = "계획이 거부되었습니다. 이유: "
REJECTION_SUFFIX = ". 어떤 작업도 시뮬레이션되거나 실행되지 않았습니다."
