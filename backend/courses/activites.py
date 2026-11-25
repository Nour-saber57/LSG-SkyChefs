
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
    select,
    update,
)

from sqlalchemy.orm import Mapped, Session, mapped_column


if __package__ == "activities":
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

    @model_validator(mode="after")
    def validate_dates(self):

        if self.end_date < self.start_date:

            raise ValueError(
                "End date must be on or after start date."
            )

        return self


# ==========================================
# RESPONSE MODELS
# ==========================================

class ActivityView(ActivityCreate):

    model_config = ConfigDict(from_attributes=True)

    id: int


class AdminActivityView(ActivityView):

    created_by: int

    created_at: int

    archived_at: int | None


# ==========================================
# API ROUTER
# ==========================================

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
            **payload.model_dump(),
            created_by=admin.id,
            created_at=int(time.time())
        )

        db.add(entry)

        db.commit()

        db.refresh(entry)

        return entry


    # ======================================
    # EMPLOYEE: VIEW PUBLISHED ACTIVITIES
    # ======================================

    @router.get(
        "/api/v1/activities",
        response_model=list[ActivityView],
        dependencies=[Depends(require_user)],
    )
    def employee_activities(
        db: Session = Depends(get_db),
        limit: int = Query(25, ge=1, le=100),
        before_id: int | None = Query(None, gt=0),
    ):

        query = select(Activity).where(
            Activity.archived_at.is_(None)
        )

        if before_id is not None:

            query = query.where(
                Activity.id < before_id
            )

        return db.scalars(
            query.order_by(
                Activity.id.desc()
            ).limit(limit)
        ).all()


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

        return db.scalars(
            query.order_by(
                Activity.id.desc()
            ).limit(limit)
        ).all()


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
