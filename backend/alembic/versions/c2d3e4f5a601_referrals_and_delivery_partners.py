"""referrals and delivery partners

Revision ID: c2d3e4f5a601
Revises: b1c2d3e4f501
Create Date: 2026-10-27 01:58:08.828194

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a601'
down_revision: str | None = 'b1c2d3e4f501'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('delivery_partner_profiles',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('status', sa.String(length=12), server_default='ACTIVE', nullable=False),
    sa.Column('availability', sa.String(length=12), server_default='OFFLINE', nullable=False),
    sa.Column('vehicle_type', sa.String(length=10), server_default='BIKE', nullable=False),
    sa.Column('vehicle_number', sa.String(length=30), nullable=True),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("availability IN ('OFFLINE', 'AVAILABLE', 'ON_DELIVERY')", name='ck_dpp_availability'),
    sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED')", name='ck_dpp_status'),
    sa.CheckConstraint("vehicle_type IN ('BIKE', 'SCOOTER', 'BICYCLE', 'VAN', 'OTHER')", name='ck_dpp_vehicle'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', name='uq_delivery_partner_profiles_user_id')
    )
    op.create_table('referral_codes',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('code', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('char_length(code) >= 6', name='ck_referral_codes_length'),
    sa.CheckConstraint('code = upper(code)', name='ck_referral_codes_upper'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', name='uq_referral_codes_code'),
    sa.UniqueConstraint('user_id', name='uq_referral_codes_user_id')
    )
    op.create_table('referrals',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('referrer_user_id', sa.BigInteger(), nullable=False),
    sa.Column('referred_user_id', sa.BigInteger(), nullable=False),
    sa.Column('referral_code_id', sa.BigInteger(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
    sa.Column('qualifying_order_id', sa.BigInteger(), nullable=True),
    sa.Column('applied_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('qualified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rewarded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reversed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status_reason', sa.String(length=300), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('PENDING', 'QUALIFIED', 'REWARDED', 'REVERSED', 'CANCELLED')", name='ck_referrals_status'),
    sa.CheckConstraint('referrer_user_id <> referred_user_id', name='ck_referrals_no_self'),
    sa.ForeignKeyConstraint(['qualifying_order_id'], ['orders.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['referral_code_id'], ['referral_codes.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['referred_user_id'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['referrer_user_id'], ['users.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('qualifying_order_id', name='uq_referrals_qualifying_order_id'),
    sa.UniqueConstraint('referred_user_id', name='uq_referrals_referred_user_id')
    )
    op.create_index('ix_referrals_referrer_user_id', 'referrals', ['referrer_user_id'], unique=False)
    op.create_index('ix_referrals_status', 'referrals', ['status'], unique=False)
    op.create_table('delivery_assignments',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('order_id', sa.BigInteger(), nullable=False),
    sa.Column('fulfillment_id', sa.BigInteger(), nullable=False),
    sa.Column('partner_user_id', sa.BigInteger(), nullable=False),
    sa.Column('assigned_by_user_id', sa.BigInteger(), nullable=True),
    sa.Column('status', sa.String(length=20), server_default='ASSIGNED', nullable=False),
    sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('picked_up_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('out_for_delivery_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('close_reason', sa.String(length=300), nullable=True),
    sa.Column('cod_status', sa.String(length=15), server_default='NOT_APPLICABLE', nullable=False),
    sa.Column('cod_expected_amount', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('cod_collected_amount', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('cod_collected_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cod_reconciled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cod_reconciled_by_user_id', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("cod_status <> 'COD_COLLECTED' OR cod_collected_amount = cod_expected_amount", name='ck_da_cod_collected_exact'),
    sa.CheckConstraint("cod_status IN ('NOT_APPLICABLE', 'COD_PENDING', 'COD_COLLECTED', 'COD_FAILED')", name='ck_da_cod_status'),
    sa.CheckConstraint("status <> 'DELIVERED' OR cod_status IN ('NOT_APPLICABLE', 'COD_COLLECTED')", name='ck_da_delivered_cod_settled'),
    sa.CheckConstraint("status IN ('ASSIGNED', 'ACCEPTED', 'PICKED_UP', 'OUT_FOR_DELIVERY', 'DELIVERED', 'FAILED', 'REJECTED', 'CANCELLED')", name='ck_da_status'),
    sa.CheckConstraint('cod_expected_amount >= 0', name='ck_da_cod_expected'),
    sa.ForeignKeyConstraint(['assigned_by_user_id'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['cod_reconciled_by_user_id'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['fulfillment_id'], ['fulfillments.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['partner_user_id'], ['users.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_delivery_assignments_order_id', 'delivery_assignments', ['order_id'], unique=False)
    op.create_index('ix_delivery_assignments_partner_status', 'delivery_assignments', ['partner_user_id', 'status'], unique=False)
    op.create_index('uq_delivery_assignments_one_active_per_order', 'delivery_assignments', ['order_id'], unique=True, postgresql_where=sa.text("status IN ('ASSIGNED', 'ACCEPTED', 'PICKED_UP', 'OUT_FOR_DELIVERY')"))
    op.create_table('referral_reward_ledger',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('referral_id', sa.BigInteger(), nullable=False),
    sa.Column('beneficiary_user_id', sa.BigInteger(), nullable=False),
    sa.Column('beneficiary_role', sa.String(length=10), nullable=False),
    sa.Column('entry_type', sa.String(length=10), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), server_default='INR', nullable=False),
    sa.Column('order_id', sa.BigInteger(), nullable=True),
    sa.Column('reason', sa.String(length=300), nullable=True),
    sa.Column('created_by_user_id', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(entry_type = 'REWARD' AND amount > 0) OR (entry_type = 'REVERSAL' AND amount < 0)", name='ck_referral_ledger_sign'),
    sa.CheckConstraint("beneficiary_role IN ('REFERRER', 'REFERRED')", name='ck_referral_ledger_role'),
    sa.CheckConstraint("entry_type IN ('REWARD', 'REVERSAL')", name='ck_referral_ledger_type'),
    sa.ForeignKeyConstraint(['beneficiary_user_id'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['referral_id'], ['referrals.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('referral_id', 'beneficiary_user_id', 'entry_type', name='uq_referral_ledger_once')
    )
    op.create_index('ix_referral_ledger_beneficiary', 'referral_reward_ledger', ['beneficiary_user_id'], unique=False)
    op.create_table('delivery_partner_earnings',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('assignment_id', sa.BigInteger(), nullable=False),
    sa.Column('partner_user_id', sa.BigInteger(), nullable=False),
    sa.Column('order_id', sa.BigInteger(), nullable=False),
    sa.Column('entry_type', sa.String(length=10), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('rule_version', sa.String(length=30), nullable=False),
    sa.Column('base_amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('per_km_amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('billable_km', sa.Integer(), server_default='0', nullable=False),
    sa.Column('cod_bonus', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('reason', sa.String(length=300), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(entry_type = 'EARNING' AND amount >= 0) OR (entry_type = 'REVERSAL' AND amount <= 0)", name='ck_dpe_sign'),
    sa.CheckConstraint("entry_type IN ('EARNING', 'REVERSAL')", name='ck_dpe_type'),
    sa.ForeignKeyConstraint(['assignment_id'], ['delivery_assignments.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['partner_user_id'], ['users.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('assignment_id', 'entry_type', name='uq_dpe_assignment_entry')
    )
    op.create_index('ix_dpe_partner', 'delivery_partner_earnings', ['partner_user_id', 'created_at'], unique=False)
    op.create_table('delivery_partner_locations',
    sa.Column('assignment_id', sa.BigInteger(), nullable=False),
    sa.Column('partner_user_id', sa.BigInteger(), nullable=False),
    sa.Column('latitude', sa.Float(), nullable=False),
    sa.Column('longitude', sa.Float(), nullable=False),
    sa.Column('accuracy_m', sa.Float(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('latitude BETWEEN -90 AND 90', name='ck_dpl_lat'),
    sa.CheckConstraint('longitude BETWEEN -180 AND 180', name='ck_dpl_lng'),
    sa.ForeignKeyConstraint(['assignment_id'], ['delivery_assignments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['partner_user_id'], ['users.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('assignment_id')
    )
    # Append-only ledgers: the database rejects UPDATE/DELETE whatever the app does.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION gb_referral_ledger_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'referral_reward_ledger is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_referral_ledger_immutable BEFORE UPDATE OR DELETE ON "
        "referral_reward_ledger FOR EACH ROW EXECUTE FUNCTION gb_referral_ledger_immutable()"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION gb_partner_earnings_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'delivery_partner_earnings is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_partner_earnings_immutable BEFORE UPDATE OR DELETE ON "
        "delivery_partner_earnings FOR EACH ROW EXECUTE FUNCTION gb_partner_earnings_immutable()"
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_partner_earnings_immutable ON delivery_partner_earnings")
    op.execute("DROP TRIGGER IF EXISTS trg_referral_ledger_immutable ON referral_reward_ledger")
    op.drop_table('delivery_partner_locations')
    op.drop_index('ix_dpe_partner', table_name='delivery_partner_earnings')
    op.drop_table('delivery_partner_earnings')
    op.drop_index('ix_referral_ledger_beneficiary', table_name='referral_reward_ledger')
    op.drop_table('referral_reward_ledger')
    op.drop_index('uq_delivery_assignments_one_active_per_order', table_name='delivery_assignments', postgresql_where=sa.text("status IN ('ASSIGNED', 'ACCEPTED', 'PICKED_UP', 'OUT_FOR_DELIVERY')"))
    op.drop_index('ix_delivery_assignments_partner_status', table_name='delivery_assignments')
    op.drop_index('ix_delivery_assignments_order_id', table_name='delivery_assignments')
    op.drop_table('delivery_assignments')
    op.drop_index('ix_referrals_status', table_name='referrals')
    op.drop_index('ix_referrals_referrer_user_id', table_name='referrals')
    op.drop_table('referrals')
    op.drop_table('referral_codes')
    op.drop_table('delivery_partner_profiles')
    # ### end Alembic commands ###
    op.execute("DROP FUNCTION IF EXISTS gb_partner_earnings_immutable()")
    op.execute("DROP FUNCTION IF EXISTS gb_referral_ledger_immutable()")
