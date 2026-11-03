"""
Papéis e permissões.

Mantém o padrão "permissão por rota" do interno-crm, mas sem tabelas de RBAC:
o mapeamento papel -> permissões vive em código. Quando precisar de papéis
dinâmicos, troque `permissions_for_role` por uma consulta ao banco.

Convenção de nomes: "<recurso>:<ação>" (ex.: "workout:read").
"""

ROLE_USER = "user"
ROLE_ADMIN = "admin"

_USER_PERMISSIONS = frozenset({"profile:read", "profile:write", "workouts:read", "workouts:write"})

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    ROLE_USER: _USER_PERMISSIONS,
    # "exercises:manage" = gerir o catálogo global de exercícios (só admin)
    ROLE_ADMIN: _USER_PERMISSIONS | {"user:read", "user:write", "exercises:manage"},
}


def permissions_for_role(role: str) -> list[str]:
    return sorted(ROLE_PERMISSIONS.get(role, frozenset()))
