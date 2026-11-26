
import time
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    model_validator,
)

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    or_,
    select,
    update,
)

from sqlalchemy.orm import Mapped, Session, mapped_column


if __package__ == "courses":
    from database import Base, User
else:
    from ..database import Base, User


# ==========================================
# DATABASE MODEL
# ==========================================

class Activity(Base):

    __tablename__ = "activities"

    __table_args__ = (
        CheckConstraint(
            "kind IN ('activity', 'program')",
            name="ck_activity_kind"
        ),
        CheckConstraint(
            "end_date >= start_date",
            name="ck_activity_dates"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str] = mapped_column(String(150))

    kind: Mapped[str] = mapped_column(String(20))

    description: Mapped[str] = mapped_column(Text)

    start_date: Mapped[date] = mapped_column(Date)

    end_date: Mapped[date] = mapped_column(Date)

    location: Mapped[str] = mapped_column(String(150))

    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id")
    )

    created_at: Mapped[int] = mapped_column(Integer)

    archived_at: Mapped[int | None] = mapped_column(
        Integer,
        index=True
    )


class ActivityRecipient(Base):

    __tablename__ = "activity_recipients"

    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id"),
        primary_key=True,
    )

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        primary_key=True,
    )


# ==========================================
# REQUEST VALIDATION
# ==========================================

class ActivityCreate(BaseModel):

    model_config = ConfigDict(extra="forbid")

    title: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=150
        ),
    ]

    kind: Literal["activity", "program"]

    description: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=5000
        ),
    ]

    start_date: date

    end_date: date

    location: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=150
        ),
    ]

    employee_ids: list[int] | None = None

    @model_validator(mode="after")
    def validate_dates(self):

        if self.end_date < self.start_date:

            raise ValueError(
                "End date must be on or after start date."
            )

        if self.employee_ids is not None and (
            not self.employee_ids
            or len(set(self.employee_ids)) != len(self.employee_ids)
        ):
            raise ValueError(
                "Select at least one employee without duplicate selections."
            )

        return self


# ==========================================
# RESPONSE MODELS
# ==========================================

class ActivityView(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    kind: Literal["activity", "program"]
    description: str
    start_date: date
    end_date: date
    location: str


class ActivityEmployeeView(BaseModel):

    id: int
    name: str
    identity: str


class AdminActivityView(ActivityView):

    created_by: int

    created_at: int

    archived_at: int | None

    employee_ids: list[int]

    employee_names: list[str]

    all_employees: bool


# ==========================================
# API ROUTER
# ==========================================

def _admin_activity_views(activities: list[Activity], db: Session):
    activity_ids = [activity.id for activity in activities]
    recipients_by_activity: dict[int, list[tuple[int, str]]] = {}
    if activity_ids:
        rows = db.execute(
            select(
                ActivityRecipient.activity_id,
                User.id,
                User.name,
            )
            .join(User, User.id == ActivityRecipient.employee_id)
            .where(ActivityRecipient.activity_id.in_(activity_ids))
            .order_by(User.name, User.id)
        )
        for activity_id, employee_id, employee_name in rows:
            recipients_by_activity.setdefault(activity_id, []).append(
                (employee_id, employee_name)
            )

    return [
        AdminActivityView(
            **ActivityView.model_validate(activity).model_dump(),
            created_by=activity.created_by,
            created_at=activity.created_at,
            archived_at=activity.archived_at,
            employee_ids=[
                employee_id
                for employee_id, _ in recipients_by_activity.get(activity.id, [])
            ],
            employee_names=[
                employee_name
                for _, employee_name in recipients_by_activity.get(activity.id, [])
            ],
            all_employees=activity.id not in recipients_by_activity,
        )
        for activity in activities
    ]


def create_activities_router(
    get_db,
    require_user,
    require_admin,
    require_csrf
):

    router = APIRouter(tags=["Activities"])


    # ======================================
    # ADMIN: CREATE ACTIVITY OR PROGRAM
    # ======================================

    @router.post(
        "/api/v1/admin/activities",
        status_code=201,
        response_model=AdminActivityView,
        dependencies=[Depends(require_csrf)],
    )
    def create_activity(
        payload: ActivityCreate,
        admin: User = Depends(require_admin),
        db: Session = Depends(get_db),
    ):

        entry = Activity(
            **payload.model_dump(exclude={"employee_ids"}),
            created_by=admin.id,
            created_at=int(time.time())
        )

        db.add(entry)
        db.flush()

        selected_employees = []
        if payload.employee_ids is not None:
            selected_employees = db.scalars(
                select(User).where(
                    User.id.in_(payload.employee_ids),
                    User.role == "user",
                    User.active.is_(True),
                )
            ).all()
            if len(selected_employees) != len(payload.employee_ids):
                db.rollback()
                raise HTTPException(
                    status_code=422,
                    detail="One or more selected employees are unavailable.",
                )
            db.add_all(
                ActivityRecipient(
                    activity_id=entry.id,
                    employee_id=employee.id,
                )
                for employee in selected_employees
            )
        db.commit()

        db.refresh(entry)

        return AdminActivityView(
            **ActivityView.model_validate(entry).model_dump(),
            created_by=entry.created_by,
            created_at=entry.created_at,
            archived_at=entry.archived_at,
            employee_ids=payload.employee_ids or [],
            employee_names=sorted(employee.name for employee in selected_employees),
            all_employees=payload.employee_ids is None,
        )


    # ======================================
    # ADMIN: SELECTABLE EMPLOYEES
    # ======================================

    @router.get(
        "/api/v1/admin/activities/recipients",
        response_model=list[ActivityEmployeeView],
        dependencies=[Depends(require_admin)],
    )
    def activity_recipients(
        db: Session = Depends(get_db),
    ):
        employees = db.scalars(
            select(User)
            .where(
                User.role == "user",
                User.active.is_(True),
            )
            .order_by(User.name, User.id)
        ).all()
        return [
            ActivityEmployeeView(
                id=employee.id,
                name=employee.name,
                identity=employee.identity,
            )
            for employee in employees
        ]


    # ======================================
    # EMPLOYEE: VIEW PUBLISHED ACTIVITIES
    # ======================================

    @router.get(
        "/api/v1/activities",
        response_model=list[ActivityView],
    )
    def employee_activities(
        employee: User = Depends(require_user),
        db: Session = Depends(get_db),
        limit: int = Query(25, ge=1, le=100),
        before_id: int | None = Query(None, gt=0),
    ):

        public_activity = ~select(
            ActivityRecipient.activity_id
        ).where(
            ActivityRecipient.activity_id == Activity.id
        ).exists()
        assigned_activity = select(
            ActivityRecipient.activity_id
        ).where(
            ActivityRecipient.activity_id == Activity.id,
            ActivityRecipient.employee_id == employee.id,
        ).exists()

        query = select(Activity).where(
            Activity.archived_at.is_(None),
            or_(public_activity, assigned_activity),
        )

        if before_id is not None:

            query = query.where(
                Activity.id < before_id
            )

        activities = db.scalars(
            query.order_by(
                Activity.id.desc()
            ).limit(limit)
        ).all()
        return activities


    # ======================================
    # ADMIN: VIEW ALL ACTIVITIES
    # ======================================

    @router.get(
        "/api/v1/admin/activities",
        response_model=list[AdminActivityView],
        dependencies=[Depends(require_admin)],
    )
    def admin_activities(
        db: Session = Depends(get_db),
        archived: bool = False,
        limit: int = Query(25, ge=1, le=100),
        before_id: int | None = Query(None, gt=0),
    ):

        query = select(Activity).where(
            Activity.archived_at.is_not(None)
            if archived
            else Activity.archived_at.is_(None)
        )

        if before_id is not None:

            query = query.where(
                Activity.id < before_id
            )

        activities = db.scalars(
            query.order_by(
                Activity.id.desc()
            ).limit(limit)
        ).all()
        return _admin_activity_views(activities, db)


    # ======================================
    # ADMIN: ARCHIVE ACTIVITY
    # ======================================

    @router.delete(
        "/api/v1/admin/activities/{activity_id}",
        status_code=204,
        dependencies=[
            Depends(require_admin),
            Depends(require_csrf)
        ],
    )
    def archive_activity(
        activity_id: int,
        db: Session = Depends(get_db),
    ):

        result = db.execute(
            update(Activity)
            .where(
                Activity.id == activity_id,
                Activity.archived_at.is_(None)
            )
            .values(
                archived_at=int(time.time())
            )
        )

        if not result.rowcount:

            db.rollback()

            raise HTTPException(
                status_code=404,
                detail="Active activity not found."
            )

        db.commit()


    return router
