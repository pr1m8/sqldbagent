"""Create the demo application schema."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260401_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create demo tables, a demo view, and seed data."""

    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("segment", sa.String(length=64), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku", sa.String(length=32), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False
        ),
        sa.Column("order_number", sa.String(length=32), nullable=False, unique=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column(
            "currency_code", sa.String(length=3), nullable=False, server_default="USD"
        ),
    )
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column(
            "product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "discount_amount", sa.Numeric(10, 2), nullable=False, server_default="0"
        ),
    )
    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False
        ),
        sa.Column("ticket_number", sa.String(length=32), nullable=False, unique=True),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_index("ix_orders_customer_id", "orders", ["customer_id"], unique=False)
    op.create_index(
        "ix_order_items_order_id", "order_items", ["order_id"], unique=False
    )
    op.create_index(
        "ix_order_items_product_id", "order_items", ["product_id"], unique=False
    )
    op.create_index(
        "ix_support_tickets_customer_id",
        "support_tickets",
        ["customer_id"],
        unique=False,
    )

    op.execute(sa.text("""
            INSERT INTO customers (id, customer_code, name, segment, country_code, is_active)
            VALUES
              (1, 'CUST-001', 'Acme Analytics', 'enterprise', 'US', true),
              (2, 'CUST-002', 'Northwind Research', 'mid_market', 'CA', true),
              (3, 'CUST-003', 'Orbit Retail', 'smb', 'GB', false)
            """))
    op.execute(sa.text("""
            INSERT INTO products (id, sku, name, category, unit_price, is_active)
            VALUES
              (1, 'SKU-ANALYTICS', 'Analytics Suite', 'software', 1299.00, true),
              (2, 'SKU-SUPPORT', 'Premium Support', 'service', 399.00, true),
              (3, 'SKU-TRAINING', 'Team Training', 'service', 899.00, true)
            """))
    op.execute(sa.text("""
            INSERT INTO orders (id, customer_id, order_number, status, order_date, currency_code)
            VALUES
              (1, 1, 'SO-1001', 'paid', DATE '2026-01-15', 'USD'),
              (2, 1, 'SO-1002', 'open', DATE '2026-02-02', 'USD'),
              (3, 2, 'SO-1003', 'paid', DATE '2026-02-14', 'CAD')
            """))
    op.execute(sa.text("""
            INSERT INTO order_items (id, order_id, product_id, quantity, unit_price, discount_amount)
            VALUES
              (1, 1, 1, 1, 1299.00, 0),
              (2, 1, 2, 1, 399.00, 50.00),
              (3, 2, 3, 2, 899.00, 0),
              (4, 3, 1, 1, 1299.00, 100.00)
            """))
    op.execute(sa.text("""
            INSERT INTO support_tickets (id, customer_id, ticket_number, priority, status, subject)
            VALUES
              (1, 1, 'TCK-1001', 'high', 'open', 'Billing discrepancy on premium support'),
              (2, 2, 'TCK-1002', 'medium', 'resolved', 'Clarification on analytics export limits')
            """))
    op.execute(sa.text("""
            CREATE VIEW customer_order_summary AS
            SELECT
              c.id AS customer_id,
              c.customer_code,
              c.name AS customer_name,
              COUNT(o.id) AS order_count,
              COALESCE(SUM((oi.quantity * oi.unit_price) - oi.discount_amount), 0) AS gross_revenue
            FROM customers AS c
            LEFT JOIN orders AS o ON o.customer_id = c.id
            LEFT JOIN order_items AS oi ON oi.order_id = o.id
            GROUP BY c.id, c.customer_code, c.name
            """))


def downgrade() -> None:
    """Drop demo tables and view."""

    op.execute(sa.text("DROP VIEW IF EXISTS customer_order_summary"))
    op.drop_index("ix_support_tickets_customer_id", table_name="support_tickets")
    op.drop_index("ix_order_items_product_id", table_name="order_items")
    op.drop_index("ix_order_items_order_id", table_name="order_items")
    op.drop_index("ix_orders_customer_id", table_name="orders")
    op.drop_table("support_tickets")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("products")
    op.drop_table("customers")
