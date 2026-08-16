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
        "A pesquisa na web não está c"
        "onfigurada nesta instância d"
        "o House Brain."
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
    "authorization_code": (
        "o código está ausente, malfo"
        "rmado ou incorreto"
    ),
    "kill_switch": (
        "a execução real está desativ"
        "ada pelo interruptor de segu"
        "rança"
    ),
    "mode": (
        "o modo solicitado não está a"
        "utorizado"
    ),
    "explicit_entity": (
        "a entidade proposta não corr"
        "esponde ao ID de entidade so"
        "licitado"
    ),
    "unresolved": (
        "o nome do dispositivo não fo"
        "i resolvido pelo servidor"
    ),
    "no_target": (
        "a pesquisa não identificou u"
        "ma única entidade controláve"
        "l"
    ),
    "resolved_entity": (
        "a entidade proposta não corr"
        "esponde à resolução do servi"
        "dor"
    ),
    "not_included": (
        "o ID de entidade solicitado "
        "não é controlável"
    ),
    "action": (
        "a ação solicitada não está a"
        "utorizada pela política"
    ),
    "value": (
        "um valor solicitado não está"
        " autorizado pela política"
    ),
    "parameter": (
        "um parâmetro solicitado não "
        "está autorizado pela polític"
        "a"
    ),
    "invalid": (
        "o comando gerado é inválido"
    ),
    "policy": (
        "a política do servidor rejei"
        "tou o plano"
    ),
}

REJECTION_PREFIX = "O plano foi rejeitado porque "
REJECTION_SUFFIX = "; nenhuma ação foi simulada ou executada."

