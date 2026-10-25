"""Include article content revision in the analysis identity."""

from alembic import op
import sqlalchemy as sa

revision = "0002_news_revision"
down_revision = "0001_product"
branch_labels = None
depends_on = None


def upgrade():
    constraints = sa.inspect(op.get_bind()).get_unique_constraints("stored_insights")
    previous = next(
        c["name"]
        for c in constraints
        if set(c["column_names"]) == {"news_id", "company_id", "role", "version"}
    )
    convention = {"uq": "uq_%(table_name)s_%(column_0_name)s"}
    with op.batch_alter_table("stored_insights", naming_convention=convention) as batch:
        batch.add_column(
            sa.Column(
                "content_version",
                sa.String(64),
                nullable=False,
                server_default="legacy",
            )
        )
        batch.drop_constraint(previous or "uq_stored_insights_news_id", type_="unique")
        batch.create_unique_constraint(
            "uq_insight_result",
            ["news_id", "company_id", "role", "version", "content_version"],
        )


def downgrade():
    raise RuntimeError(
        "Restore backup into a separate database instead of destructive downgrade"
    )
