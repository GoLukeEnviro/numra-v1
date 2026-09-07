from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import (
    Calculation,
    Person,
    PersonalTask,
    PrivateNote,
    PrivateReflection,
    Report,
    ReportSection,
)
from numra_api.models.enums import PersonalTaskStatus


class WorkspaceOverview:
    """Plain data holder for the counts/latest rows `get_workspace_overview` gathers
    -- routes/workspace.py maps this onto `WorkspaceOverviewOut`. Not a Pydantic
    model itself since some fields are ORM rows, not yet serialized shapes."""

    def __init__(
        self,
        *,
        person: Person,
        latest_calculation: Calculation | None,
        reports_total: int,
        latest_report: Report | None,
        latest_report_person: Person | None,
        latest_report_word_count: int,
        reflections_total: int,
        latest_reflection: PrivateReflection | None,
        notes_total: int,
        tasks_total: int,
        tasks_active: int,
    ) -> None:
        self.person = person
        self.latest_calculation = latest_calculation
        self.reports_total = reports_total
        self.latest_report = latest_report
        self.latest_report_person = latest_report_person
        self.latest_report_word_count = latest_report_word_count
        self.reflections_total = reflections_total
        self.latest_reflection = latest_reflection
        self.notes_total = notes_total
        self.tasks_total = tasks_total
        self.tasks_active = tasks_active


async def get_workspace_overview(
    db: AsyncSession, *, person: Person, user_id: uuid.UUID
) -> WorkspaceOverview:
    """Count + latest-row queries for every Personal-Workspace section, all scoped by
    `person.id` + `user_id` in one step per query -- same IDOR pattern as
    repositories/people.py. The caller (routes/workspace.py) already resolved
    `person` via `get_person(db, person_id=..., user_id=...)`, so every query here
    trusts `person.id` for the person-scoping but still re-applies `user_id` as the
    security filter on each table, matching the discipline elsewhere in this
    codebase (never a bare person_id-only filter)."""
    person_id = person.id

    latest_calculation_stmt = (
        select(Calculation)
        .join(Person, Person.id == Calculation.person_id)
        .where(Calculation.person_id == person_id, Person.user_id == user_id)
        .order_by(Calculation.created_at.desc())
        .limit(1)
    )
    latest_calculation = (await db.execute(latest_calculation_stmt)).scalar_one_or_none()

    reports_total_stmt = (
        select(func.count(Report.id))
        .join(Calculation, Calculation.id == Report.calculation_id)
        .where(Calculation.person_id == person_id, Report.user_id == user_id)
    )
    reports_total = (await db.execute(reports_total_stmt)).scalar_one()

    word_count_subquery = (
        select(func.coalesce(func.sum(ReportSection.word_count), 0))
        .where(ReportSection.report_id == Report.id)
        .correlate(Report)
        .scalar_subquery()
    )
    latest_report_stmt = (
        select(Report, Person, word_count_subquery)
        .join(Calculation, Calculation.id == Report.calculation_id)
        .join(Person, Person.id == Calculation.person_id)
        .where(Calculation.person_id == person_id, Report.user_id == user_id)
        .order_by(Report.created_at.desc())
        .limit(1)
    )
    latest_report_row = (await db.execute(latest_report_stmt)).first()
    if latest_report_row:
        latest_report, latest_report_person, latest_report_word_count = latest_report_row
    else:
        latest_report, latest_report_person, latest_report_word_count = None, None, 0

    reflections_total_stmt = select(func.count(PrivateReflection.id)).where(
        PrivateReflection.person_id == person_id, PrivateReflection.user_id == user_id
    )
    reflections_total = (await db.execute(reflections_total_stmt)).scalar_one()

    latest_reflection_stmt = (
        select(PrivateReflection)
        .where(PrivateReflection.person_id == person_id, PrivateReflection.user_id == user_id)
        .order_by(PrivateReflection.entry_date.desc(), PrivateReflection.created_at.desc())
        .limit(1)
    )
    latest_reflection = (await db.execute(latest_reflection_stmt)).scalar_one_or_none()

    notes_total_stmt = select(func.count(PrivateNote.id)).where(
        PrivateNote.person_id == person_id, PrivateNote.user_id == user_id
    )
    notes_total = (await db.execute(notes_total_stmt)).scalar_one()

    tasks_total_stmt = select(func.count(PersonalTask.id)).where(
        PersonalTask.person_id == person_id, PersonalTask.user_id == user_id
    )
    tasks_total = (await db.execute(tasks_total_stmt)).scalar_one()

    tasks_active_stmt = select(func.count(PersonalTask.id)).where(
        PersonalTask.person_id == person_id,
        PersonalTask.user_id == user_id,
        PersonalTask.status == PersonalTaskStatus.ACTIVE,
    )
    tasks_active = (await db.execute(tasks_active_stmt)).scalar_one()

    return WorkspaceOverview(
        person=person,
        latest_calculation=latest_calculation,
        reports_total=reports_total,
        latest_report=latest_report,
        latest_report_person=latest_report_person,
        latest_report_word_count=latest_report_word_count,
        reflections_total=reflections_total,
        latest_reflection=latest_reflection,
        notes_total=notes_total,
        tasks_total=tasks_total,
        tasks_active=tasks_active,
    )
