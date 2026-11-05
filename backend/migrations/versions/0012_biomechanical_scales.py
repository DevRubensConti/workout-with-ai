"""Versioned regional biomechanical demand criteria.

Revision ID: 0012
Revises: 0011
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

# Historical seed: future changes belong in new versions, not in this migration.
INITIAL_DEFINITION = {
    "title": "Escala de Demanda Biomecânica Regional",
    "disclaimer": (
        "Classificação interna e ordinal da exigência mecânica estimada, não da probabilidade "
        "de lesão. Não é uma escala clínica validada. Nota alta não significa contraindicação "
        "e nota baixa não garante segurança. A classificação inicial requer revisão profissional."
    ),
    "reference_conditions": (
        "Avaliar a variação específica, equipamento, apoios e amplitude descritos no cadastro. "
        "Considerar técnica controlada conforme as instruções, sem pressupor carga máxima, "
        "fadiga extrema ou execução inadequada. A carga real, o volume, a recuperação e as "
        "condições individuais devem ser considerados separadamente."
    ),
    "evaluation_criteria": (
        "Justificar a nota considerando: movimento resistido; sustentação e transmissão "
        "de carga; exigência de estabilização; apoios e alavancas; amplitude e posição. "
        "Esses fatores orientam a avaliação, mas não devem ser somados automaticamente. "
        "Comparar variações semelhantes sob as mesmas condições de referência."
    ),
    "consistency_rules": (
        "Não copiar notas apenas pelo grupo muscular. Participação estabilizadora pode ter "
        "demanda alta. Não converter notas em percentuais de risco, nem somar regiões para "
        "produzir risco total. Notas 4 e 5 exigem justificativa biomecânica explícita; nota 5 "
        "exige revisão profissional. Sugestões da IA permanecem pendentes até revisão humana. "
        "Registrar a versão dos critérios, a origem e a justificativa de cada avaliação."
    ),
    "unassessed_guidance": (
        "Informação insuficiente significa não avaliado: nota NULL e motivo registrado. "
        "Não inventar notas, não assumir zero e não tratar ausência de avaliação como segurança. "
        "Nota zero só pode resultar de avaliação explícita."
    ),
    "regions": [
        {
            "code": "shoulder",
            "label": "Ombros",
            "description": "Demanda mecânica na região dos ombros.",
        },
        {
            "code": "lumbar_spine",
            "label": "Coluna lombar",
            "description": "Demanda mecânica na região lombar, incluindo estabilização do tronco.",
        },
        {
            "code": "cervical_spine",
            "label": "Coluna cervical",
            "description": (
                "Demanda mecânica na região cervical, incluindo sustentação e estabilização."
            ),
        },
        {
            "code": "knee",
            "label": "Joelhos",
            "description": "Demanda mecânica na região dos joelhos.",
        },
        {
            "code": "elbow",
            "label": "Cotovelos",
            "description": "Demanda mecânica na região dos cotovelos.",
        },
    ],
    "roles": [
        {
            "code": "direct",
            "label": "Direta",
            "description": "Região envolvida no movimento resistido principal.",
        },
        {
            "code": "secondary",
            "label": "Secundária",
            "description": "Região que participa de movimentos associados.",
        },
        {
            "code": "stabilizing",
            "label": "Estabilizadora",
            "description": "Região que mantém posição e alinhamento; pode receber nota alta.",
        },
    ],
    "scores": [
        {
            "score": 0,
            "label": "Desprezível",
            "description": (
                "Sem participação mecânica relevante na execução descrita. Exige avaliação "
                "explícita e nunca deve ser usada como valor padrão."
            ),
        },
        {
            "score": 1,
            "label": "Baixa",
            "description": (
                "Participação discreta, com pouca exigência de movimento ou estabilização regional."
            ),
        },
        {
            "score": 2,
            "label": "Moderada",
            "description": (
                "Participação perceptível no movimento ou na estabilização, sem ser uma das "
                "principais regiões mecanicamente exigidas."
            ),
        },
        {
            "score": 3,
            "label": "Relevante",
            "description": (
                "Sustenta ou transmite resistência de forma importante; sua demanda deve ser "
                "considerada na organização do treino."
            ),
        },
        {
            "score": 4,
            "label": "Alta",
            "description": (
                "Entre as principais regiões exigidas, por movimento resistido ou estabilização "
                "substancial. Exige justificativa biomecânica explícita."
            ),
        },
        {
            "score": 5,
            "label": "Muito alta",
            "description": (
                "Demanda especialmente acentuada na variação descrita, em comparação com "
                "alternativas semelhantes. Uso excepcional, com justificativa detalhada "
                "e revisão profissional."
            ),
        },
    ],
}


def upgrade() -> None:
    table = op.create_table(
        "biomechanical_scale_versions",
        sa.Column("version", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("change_reason", sa.String(1000), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("version"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("version > 0", name="ck_biomechanical_scale_version"),
        sa.CheckConstraint("length(trim(change_reason)) > 0", name="ck_biomechanical_scale_reason"),
    )
    seed = {
        "version": 1,
        "definition": INITIAL_DEFINITION,
        "change_reason": "Formalização inicial; critérios sujeitos a revisão profissional.",
        "created_by": None,
    }
    if op.get_context().as_sql:
        # SQLAlchemy cannot render JSON literals when generating an offline SQL script.
        op.execute(
            table.insert().values(
                **{
                    key: op.inline_literal(value)
                    for key, value in {
                        **seed,
                        "definition": json.dumps(INITIAL_DEFINITION, ensure_ascii=False),
                    }.items()
                }
            )
        )
    else:
        op.bulk_insert(table, [seed])
    if op.get_context().dialect.name == "postgresql":
        op.execute("ALTER TABLE biomechanical_scale_versions ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("biomechanical_scale_versions")
