"""initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. learning_outcomes
    op.create_table(
        'learning_outcomes',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('text', sa.String(), nullable=False),
        sa.Column('concept', sa.String(), nullable=False),
        sa.Column('source_evidence', sa.String(), nullable=False),
        sa.Column('context_hash', sa.String(), nullable=False),
        if_not_exists=True,
    )
    op.create_index('ix_learning_outcomes_context_hash', 'learning_outcomes', ['context_hash'], unique=False, if_not_exists=True)

    # 2. questions
    op.create_table(
        'questions',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('question_text', sa.String(), nullable=False),
        sa.Column('question_type', sa.String(), nullable=False),
        sa.Column('choices', sa.JSON(), nullable=True),
        sa.Column('correct_answer', sa.String(), nullable=False),
        sa.Column('explanation', sa.String(), nullable=False),
        sa.Column('difficulty', sa.String(), nullable=False),
        sa.Column('estimated_time_minutes', sa.Integer(), nullable=False),
        sa.Column('related_LO_ids', sa.JSON(), nullable=False),
        sa.Column('source_evidence', sa.String(), nullable=False),
        if_not_exists=True,
    )

    # 3. question_lo_links
    op.create_table(
        'question_lo_links',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('question_id', sa.UUID(as_uuid=True), sa.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lo_id', sa.UUID(as_uuid=True), sa.ForeignKey('learning_outcomes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('reason', sa.String(), nullable=False),
        if_not_exists=True,
    )
    op.create_index('ix_question_lo_links_question_id', 'question_lo_links', ['question_id'], unique=False, if_not_exists=True)
    op.create_index('ix_question_lo_links_lo_id', 'question_lo_links', ['lo_id'], unique=False, if_not_exists=True)

    # 4. evaluation_results
    op.create_table(
        'evaluation_results',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('question_id', sa.UUID(as_uuid=True), sa.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('context_grounding_score', sa.Float(), nullable=False),
        sa.Column('clarity_score', sa.Float(), nullable=False),
        sa.Column('answer_correctness_score', sa.Float(), nullable=False),
        sa.Column('explanation_correctness_score', sa.Float(), nullable=False),
        sa.Column('learning_outcome_alignment_score', sa.Float(), nullable=False),
        sa.Column('difficulty_score', sa.Float(), nullable=False),
        sa.Column('question_type_validity_score', sa.Float(), nullable=False),
        sa.Column('choices_validity_score', sa.Float(), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        if_not_exists=True,
    )
    op.create_index('ix_evaluation_results_question_id', 'evaluation_results', ['question_id'], unique=False, if_not_exists=True)
    op.create_index('ix_evaluation_results_status', 'evaluation_results', ['status'], unique=False, if_not_exists=True)


def downgrade() -> None:
    op.drop_table('evaluation_results')
    op.drop_table('question_lo_links')
    op.drop_table('questions')
    op.drop_table('learning_outcomes')
