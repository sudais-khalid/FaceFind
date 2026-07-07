"""Initial schema

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('google_sub', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('consent_given', sa.Boolean(), nullable=False),
        sa.Column('consent_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('google_sub'),
    )
    op.create_index(op.f('ix_users_google_sub'), 'users', ['google_sub'])

    # Create events table
    op.create_table(
        'events',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organizer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('event_code', sa.String(6), nullable=False),
        sa.Column('drive_folder_id', sa.String(255), nullable=False),
        sa.Column('drive_token_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('faiss_index_path', sa.String(512), nullable=True),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('files_total', sa.Integer(), nullable=False),
        sa.Column('files_indexed', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_indexed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organizer_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('event_id'),
        sa.UniqueConstraint('event_code'),
    )
    op.create_index(op.f('ix_events_event_code'), 'events', ['event_code'])

    # Create drive_files table
    op.create_table(
        'drive_files',
        sa.Column('file_id', sa.String(255), nullable=False),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(512), nullable=False),
        sa.Column('mime_type', sa.String(128), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('md5_checksum', sa.String(64), nullable=False),
        sa.Column('thumbnail_link', sa.String(2048), nullable=True),
        sa.Column('embedding_count', sa.Integer(), nullable=False),
        sa.Column('quality_flags', sa.JSON(), nullable=True),
        sa.Column('indexed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['events.event_id']),
        sa.PrimaryKeyConstraint('file_id'),
    )

    # Create face_embeddings table
    op.create_table(
        'face_embeddings',
        sa.Column('embedding_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_id', sa.String(255), nullable=False),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('embedding_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('face_index_in_image', sa.Integer(), nullable=False),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('liveness_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('faiss_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['events.event_id']),
        sa.ForeignKeyConstraint(['file_id'], ['drive_files.file_id']),
        sa.PrimaryKeyConstraint('embedding_id'),
        sa.UniqueConstraint('faiss_id'),
    )

    # Create user_probe_embeddings table
    op.create_table(
        'user_probe_embeddings',
        sa.Column('probe_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('embedding_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('liveness_score', sa.Float(), nullable=True),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.event_id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('probe_id'),
    )

    # Create search_results table
    op.create_table(
        'search_results',
        sa.Column('result_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('matched_file_ids', sa.JSON(), nullable=False),
        sa.Column('similarity_scores', sa.JSON(), nullable=False),
        sa.Column('search_timestamp', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.event_id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('result_id'),
    )

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('log_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('user_id_hash', sa.LargeBinary(), nullable=True),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('ip_hash', sa.LargeBinary(), nullable=True),
        sa.Column('outcome', sa.String(16), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('chain_hmac', sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.event_id']),
        sa.PrimaryKeyConstraint('log_id'),
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'])
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'])


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('search_results')
    op.drop_table('user_probe_embeddings')
    op.drop_table('face_embeddings')
    op.drop_table('drive_files')
    op.drop_table('events')
    op.drop_table('users')
