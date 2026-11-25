import time
import os
from io import BytesIO
from PIL import Image, UnidentifiedImageError
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint, select, func, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Mapped, Session, mapped_column

if __package__ == "courses":
    from database import Base, User
else:
    from ..database import Base, User


COURSE_IMAGES_DIR = Path(os.environ.get("COURSE_IMAGES_DIR", str(Path(__file__).resolve().parents[1] / "course_images"))).resolve()
MAX_IMAGE_SIZE = 5 * 1024 * 1024
IMAGE_SIGNATURES = {
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/webp": (None, ".webp"),
}


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text)
    start_date: Mapped[str] = mapped_column(String(10))
    end_date: Mapped[str | None] = mapped_column(String(10))
    archived_at: Mapped[int | None] = mapped_column(Integer, index=True)
    duration: Mapped[str] = mapped_column(String(100))
    location: Mapped[str] = mapped_column(String(150))
    image_path: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[int] = mapped_column(Integer)


class CourseDecision(Base):
    __tablename__ = "course_decisions"
    __table_args__ = (
        UniqueConstraint("course_id", "employee_id", name="uq_course_employee"),
        CheckConstraint("decision IN ('enrolled', 'excused')", name="ck_course_decision"),
        CheckConstraint("decision <> 'excused' OR (reason IS NOT NULL AND length(trim(reason)) > 0)", name="ck_course_excuse_reason"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    decision: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer)


class CourseDecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["enrolled", "excused"]
    reason: Annotated[str | None, StringConstraints(max_length=2000)] = None

    @model_validator(mode="after")
    def validate_reason(self):
        if self.decision == "excused" and not (self.reason and self.reason.strip()):
            raise ValueError("A reason is required when excusing yourself.")
        return self


class EmployeeCourse(BaseModel):
    id: int
    title: str
    description: str
    start_date: str
    end_date: str | None
    duration: str
    location: str
    image_url: str | None
    decision: str | None
    reason: str | None


class AdminCourseDecision(BaseModel):
    employee_id: int
    employee_name: str
    decision: str
    reason: str | None
    submitted_at: datetime


class AdminCourse(EmployeeCourse):
    created_at: datetime
    archived_at: datetime | None
    response_count: int
    enrolled_count: int
    excused_count: int


def _image_extension(content_type: str, data: bytes) -> str:
    signature, extension = IMAGE_SIGNATURES.get(content_type, (None, None))
    valid = (
        data.startswith(signature)
        if signature is not None
        else content_type == "image/webp"
        and len(data) >= 12
        and data[:4] == b"RIFF"
        and data[8:12] == b"WEBP"
    )
    if not valid:
        raise HTTPException(status_code=415, detail="Upload a valid JPEG, PNG, or WebP image.")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.width * image.height > 20_000_000 or image.format != {".jpg": "JPEG", ".png": "PNG", ".webp": "WEBP"}[extension]:
                raise ValueError("Invalid image dimensions or format")
            image.verify()
    except (ValueError, OSError, SyntaxError, Image.DecompressionBombError, UnidentifiedImageError) as error:
        raise HTTPException(status_code=415, detail="Invalid or oversized image.") from error
    return extension


def _course_response(course: Course, decision: CourseDecision | None = None):
    return EmployeeCourse(
        id=course.id,
        title=course.title,
        description=course.description,
        start_date=course.start_date,
        end_date=course.end_date,
        duration=course.duration,
        location=course.location,
        image_url=f"/api/v1/courses/{course.id}/image" if course.image_path else None,
        decision=decision.decision if decision else None,
        reason=decision.reason if decision else None,
    )


def create_courses_router(
    get_db, require_user, require_admin, require_course_viewer, require_csrf
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/api/v1/admin/courses",
        status_code=201,
        dependencies=[Depends(require_admin), Depends(require_csrf)],
    )
    async def create_course(
        title: Annotated[str, Form(min_length=1, max_length=150)],
        description: Annotated[str, Form(min_length=1, max_length=5000)],
        start_date: Annotated[str, Form(min_length=1, max_length=10)],
        end_date: Annotated[str, Form(min_length=10, max_length=10)],
        duration: Annotated[str, Form(min_length=1, max_length=100)],
        location: Annotated[str, Form(min_length=1, max_length=150)],
        image: Annotated[UploadFile | None, File()] = None,
        db: Session = Depends(get_db),
    ):
        title = title.strip()
        description = description.strip()
        start_date = start_date.strip()
        duration = duration.strip()
        location = location.strip()
        if not all((title, description, start_date, duration, location)):
            raise HTTPException(status_code=422, detail="Complete all required course details.")
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
            if end < start:
                raise ValueError("End date precedes start date")
        except ValueError as error:
            raise HTTPException(status_code=422, detail="Enter valid dates; end date must be on or after start date.") from error

        image_name = None
        if image and image.filename:
            data = await image.read(MAX_IMAGE_SIZE + 1)
            if len(data) > MAX_IMAGE_SIZE:
                raise HTTPException(status_code=413, detail="Course images must be 5 MB or smaller.")
            image_name = f"{uuid.uuid4().hex}{_image_extension(image.content_type or "", data)}"
            COURSE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            (COURSE_IMAGES_DIR / image_name).write_bytes(data)

        course = Course(
            title=title,
            description=description,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            duration=duration,
            location=location,
            image_path=image_name,
            created_at=int(time.time()),
        )
        db.add(course)
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            if image_name:
                (COURSE_IMAGES_DIR / image_name).unlink(missing_ok=True)
            raise HTTPException(status_code=409, detail="Could not save this course.")
        return {"id": course.id, "confirmation": "Course created."}

    @router.get(
        "/api/v1/courses",
        response_model=list[EmployeeCourse],
        dependencies=[Depends(require_user)],
    )
    def get_courses(
        employee: User = Depends(require_user),
        db: Session = Depends(get_db),
        offset: int = Query(0, ge=0),
        limit: int = Query(25, ge=1, le=100),
    ):
        courses = db.scalars(select(Course).where(Course.archived_at.is_(None)).order_by(Course.start_date, Course.id).offset(offset).limit(limit)).all()
        decisions = db.scalars(
            select(CourseDecision).where(CourseDecision.employee_id == employee.id, CourseDecision.course_id.in_([c.id for c in courses]))
        ).all()
        decisions_by_course = {decision.course_id: decision for decision in decisions}
        return [
            _course_response(course, decisions_by_course.get(course.id))
            for course in courses
        ]

    @router.get(
        "/api/v1/courses/{course_id}/image",
        dependencies=[Depends(require_course_viewer)],
    )
    def get_course_image(course_id: int, db: Session = Depends(get_db), viewer: User = Depends(require_course_viewer)):
        course = db.get(Course, course_id)
        if not course or not course.image_path or (course.archived_at is not None and viewer.role != "admin"):
            raise HTTPException(status_code=404, detail="Course image not found.")
        image_path = (COURSE_IMAGES_DIR / course.image_path).resolve()
        if image_path.parent != COURSE_IMAGES_DIR or not image_path.is_file():
            raise HTTPException(status_code=404, detail="Course image not found.")
        return FileResponse(image_path, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})

    @router.put(
        "/api/v1/courses/{course_id}/decision",
        response_model=EmployeeCourse,
        dependencies=[Depends(require_csrf)],
    )
    def save_course_decision(
        course_id: int,
        payload: CourseDecisionCreate,
        employee: User = Depends(require_user),
        db: Session = Depends(get_db),
    ):
        # Lock the course for the duration of the response transaction.
        # A conditional no-op UPDATE also serializes SQLite writers.
        locked = db.execute(update(Course).where(Course.id == course_id, Course.archived_at.is_(None)).values(archived_at=None))
        if not locked.rowcount:
            db.rollback()
            raise HTTPException(status_code=404, detail="Course is unavailable.")
        course = db.get(Course, course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found.")
        decision = db.scalar(
            select(CourseDecision).where(
                CourseDecision.course_id == course_id,
                CourseDecision.employee_id == employee.id,
            )
        )
        submitted_at = int(time.time())
        if decision is None:
            decision = CourseDecision(
                course_id=course_id,
                employee_id=employee.id,
                created_at=submitted_at,
            )
            db.add(decision)
        decision.decision = payload.decision
        decision.reason = payload.reason.strip() if payload.decision == "excused" else None
        decision.created_at = submitted_at
        try:
            db.commit()
        except IntegrityError as error:
            db.rollback()
            raise HTTPException(status_code=409, detail="Your course decision could not be saved.") from error
        return _course_response(course, decision)

    @router.get(
        "/api/v1/admin/courses",
        response_model=list[AdminCourse],
        dependencies=[Depends(require_admin)],
    )
    def get_admin_courses(db: Session = Depends(get_db), archived: bool = False,
                          offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)):
        condition = Course.archived_at.is_not(None) if archived else Course.archived_at.is_(None)
        courses = db.scalars(select(Course).where(condition).order_by(Course.created_at.desc(), Course.id.desc()).offset(offset).limit(limit)).all()
        counts = {}
        for course_id, decision, count in db.execute(select(CourseDecision.course_id, CourseDecision.decision, func.count()).where(CourseDecision.course_id.in_([c.id for c in courses])).group_by(CourseDecision.course_id, CourseDecision.decision)):
            counts.setdefault(course_id, {})[decision] = count
        return [AdminCourse(**_course_response(c).model_dump(),
            created_at=datetime.fromtimestamp(c.created_at, tz=timezone.utc),
            archived_at=datetime.fromtimestamp(c.archived_at, tz=timezone.utc) if c.archived_at is not None else None,
            response_count=sum(counts.get(c.id, {}).values()),
            enrolled_count=counts.get(c.id, {}).get("enrolled", 0),
            excused_count=counts.get(c.id, {}).get("excused", 0)) for c in courses]

    @router.get("/api/v1/admin/courses/{course_id}/decisions", response_model=list[AdminCourseDecision], dependencies=[Depends(require_admin)])
    def get_decisions(course_id: int, db: Session = Depends(get_db),
                      offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        if not db.get(Course, course_id):
            raise HTTPException(status_code=404, detail="Course not found.")
        rows = db.execute(select(CourseDecision, User.name).join(User, User.id == CourseDecision.employee_id).where(CourseDecision.course_id == course_id).order_by(CourseDecision.id).offset(offset).limit(limit))
        return [AdminCourseDecision(employee_id=d.employee_id, employee_name=name, decision=d.decision, reason=d.reason, submitted_at=datetime.fromtimestamp(d.created_at, tz=timezone.utc)) for d, name in rows]

    @router.delete("/api/v1/admin/courses/{course_id}", status_code=204, dependencies=[Depends(require_admin), Depends(require_csrf)])
    def archive_course(course_id: int, db: Session = Depends(get_db)):
        result = db.execute(update(Course).where(Course.id == course_id, Course.archived_at.is_(None)).values(archived_at=int(time.time())))
        if not result.rowcount and not db.get(Course, course_id):
            raise HTTPException(status_code=404, detail="Course not found.")
        db.commit()

    return router
