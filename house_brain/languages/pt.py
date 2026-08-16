"""Server-owned messages for this language."""

MESSAGES = {
    "authorization_invalid": (
        "O plano foi rejeitado porque"
        " o código de autorização est"
        "á ausente, malformado ou inc"
        "orreto; nenhuma ação foi sim"
        "ulada ou executada."
    ),
    "web_search_unavailable": (
        "A pesquisa na web não está configurada nesta instância do House Brain."
    ),
    "entity_ambiguous": (
        "O nome solicitado não identi"
        "fica uma única entidade cont"
        "rolável. Especifique o nome "
        "exato do dispositivo."
    ),
    "entity_not_found": (
        "Não encontrei nenhuma entida"
        "de correspondente ao nome so"
        "licitado. Verifique o nome d"
        "o dispositivo."
    ),
    "entity_not_controllable": (
        "A entidade solicitada existe"
        ", mas não está incluída entr"
        "e as entidades controláveis."
    ),
    "authorization_not_validated": (
        "O plano foi rejeitado porque"
        " o código fornecido não foi "
        "validado por uma ferramenta "
        "de ação; nenhuma ação foi si"
        "mulada ou executada."
    ),
    "action_not_validated": (
        "Não foi possível concluir o "
        "comando porque nenhuma ferra"
        "menta de ação o validou; nen"
        "huma ação foi simulada ou ex"
        "ecutada."
    ),
}

REJECTION_REASONS = {
    "device_code": ("o dispositivo exige o respetivo código do Home Assistant"),
    "service": ("o serviço gerado não existe no Home Assistant"),
    "authorization_code": ("o código está ausente, malformado ou incorreto"),
    "kill_switch": ("a execução real está desativada pelo interruptor de segurança"),
    "mode": ("o modo solicitado não está autorizado"),
    "explicit_entity": (
        "a entidade proposta não corresponde ao ID de entidade solicitado"
    ),
    "unresolved": ("o nome do dispositivo não foi resolvido pelo servidor"),
    "no_target": ("a pesquisa não identificou uma única entidade controlável"),
    "resolved_entity": ("a entidade proposta não corresponde à resolução do servidor"),
    "not_included": ("o ID de entidade solicitado não é controlável"),
    "action": ("a ação solicitada não está autorizada pela política"),
    "value": ("um valor solicitado não está autorizado pela política"),
    "parameter": ("um parâmetro solicitado não está autorizado pela política"),
    "invalid": ("o comando gerado é inválido"),
    "policy": ("a política do servidor rejeitou o plano"),
}

REJECTION_PREFIX = "O plano foi rejeitado porque "
REJECTION_SUFFIX = "; nenhuma ação foi simulada ou executada."
