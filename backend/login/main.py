from contextlib import asynccontextmanager
import hashlib
import secrets
import time
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from pwdlib import PasswordHash

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    create_engine,
    delete,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

from starlette.middleware.trustedhost import TrustedHostMiddleware


# --------------------------------------------------
# Configuration
# --------------------------------------------------

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        extra="ignore",
    )

    database_url: str = "sqlite:///./skychef.db"
    cookie_secure: bool = True

    frontend_origins: list[str] = [
        "http://localhost:5173"
    ]

    allowed_hosts: list[str] = [
        "localhost",
        "127.0.0.1",
    ]

    session_hours: int = Field(
        default=8,
        ge=1,
        le=24,
    )


# --------------------------------------------------
# Database models
# --------------------------------------------------

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    # An employee ID OR work email.
    identity: Mapped[str] = mapped_column(
        String(254),
        unique=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(150))

    password_hash: Mapped[str] = mapped_column(
        String(512)
    )

    # "user" or "admin"
    role: Mapped[str] = mapped_column(String(20))

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )


class LoginSession(Base):
    __tablename__ = "login_sessions"

    token_hash: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )

    csrf_hash: Mapped[str] = mapped_column(String(64))

    expires_at: Mapped[int] = mapped_column(
        Integer,
        index=True,
    )


class LoginLimit(Base):
    __tablename__ = "login_limits"

    key: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    hits: Mapped[int] = mapped_column(Integer)

    expires_at: Mapped[int] = mapped_column(
        Integer,
        index=True,
    )


# --------------------------------------------------
# Request / response schemas
# --------------------------------------------------

class Credentials(BaseModel):
    # Reject fields such as a client-supplied role.
    model_config = ConfigDict(extra="forbid")

    identity: str = Field(
        min_length=1,
        max_length=254,
    )

    password: SecretStr = Field(
        min_length=1,
        max_length=1024,
    )


class PublicUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identity: str
    name: str
    role: str


class LoginResult(BaseModel):
    user: PublicUser
    redirect_to: str
    csrf_token: str


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity: str = Field(min_length=1, max_length=254)
    name: str = Field(min_length=1, max_length=150)
    password: SecretStr = Field(min_length=12, max_length=1024)


# --------------------------------------------------
# Security utilities
# --------------------------------------------------

passwords = PasswordHash.recommended()

# Used when an account does not exist, so password
# verification still runs.
DUMMY_HASH = passwords.hash(
    secrets.token_urlsafe(32)
)

COOKIE_NAME = "skychef_session"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# --------------------------------------------------
# Application factory
# --------------------------------------------------

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    connect_args = {}
    database_url = settings.database_url

    if database_url.startswith("sqlite:///./"):
        database_file = (
            Path(__file__).resolve().parents[1]
            / database_url.removeprefix("sqlite:///./")
        )
        database_url = f"sqlite:///{database_file.as_posix()}"

    if database_url.startswith("sqlite"):
        connect_args = {
            "check_same_thread": False
        }

    engine = create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )

    session_factory = sessionmaker(
        engine,
        expire_on_commit=False,
    )

    @asynccontextmanager
    async def lifespan(app):
        # Suitable for this starter.
        # Introduce migrations before production.
        Base.metadata.create_all(engine)

        yield

        engine.dispose()

    app = FastAPI(
        title="SkyChef Authentication API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.state.session_factory = session_factory
    app.state.settings = settings

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=[
            "Content-Type",
            "X-CSRF-Token",
        ],
    )

    # --------------------------------------------------
    # Request protections
    # --------------------------------------------------

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        origin = request.headers.get("origin")

        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and origin
            and origin not in settings.frontend_origins
        ):
            return JSONResponse(
                {"detail": "Origin not allowed"},
                status_code=403,
            )

        response = await call_next(request)

        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"

        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not echo submitted passwords in errors.
        errors = [
            {
                "loc": list(error["loc"]),
                "msg": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]

        return JSONResponse(
            {"detail": errors},
            status_code=422,
        )

    # --------------------------------------------------
    # Dependencies
    # --------------------------------------------------

    def get_db():
        with session_factory() as db:
            yield db

    def get_current_session(
        request: Request,
        db: Session = Depends(get_db),
    ):
        token = request.cookies.get(COOKIE_NAME)

        login_session = (
            db.get(LoginSession, digest(token))
            if token
            else None
        )

        user = (
            db.get(User, login_session.user_id)
            if login_session
            else None
        )

        if (
            not login_session
            or login_session.expires_at <= int(time.time())
            or not user
            or not user.active
        ):
            raise HTTPException(
                status_code=401,
                detail="Sign in required",
            )

        return login_session, user

    def get_current_user(
        auth=Depends(get_current_session),
    ):
        return auth[1]

    def require_admin(
        user: User = Depends(get_current_user),
    ):
        if user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required",
            )

        return user

    def require_user(
        user: User = Depends(get_current_user),
    ):
        if user.role != "user":
            raise HTTPException(
                status_code=403,
                detail="Employee access required",
            )

        return user

    # --------------------------------------------------
    # Login throttling
    # --------------------------------------------------

    def check_rate_limit(
        db: Session,
        key: str,
        maximum: int,
        period: int,
    ):
        now = int(time.time())

        bucket = digest(
            f"{key}:{now // period}"
        )

        result = db.execute(
            update(LoginLimit)
            .where(LoginLimit.key == bucket)
            .values(hits=LoginLimit.hits + 1)
        )

        if not result.rowcount:
            db.add(
                LoginLimit(
                    key=bucket,
                    hits=1,
                    expires_at=(now // period + 1) * period,
                )
            )

            try:
                db.commit()

            except IntegrityError:
                db.rollback()

                db.execute(
                    update(LoginLimit)
                    .where(LoginLimit.key == bucket)
                    .values(hits=LoginLimit.hits + 1)
                )

        db.commit()

        item = db.get(LoginLimit, bucket)

        if item.hits > maximum:
            retry_after = max(
                1,
                item.expires_at - now,
            )

            raise HTTPException(
                status_code=429,
                detail="Too many sign-in attempts. Try again later.",
                headers={
                    "Retry-After": str(retry_after)
                },
            )

    # --------------------------------------------------
    # Shared login logic
    # --------------------------------------------------

    def perform_login(
        payload: Credentials,
        request: Request,
        response: Response,
        db: Session,
        expected_role: str | None,
    ):
        identity = payload.identity.strip().casefold()

        ip = (
            request.client.host
            if request.client
            else "unknown"
        )

        check_rate_limit(
            db,
            key=f"ip:{ip}",
            maximum=30,
            period=60,
        )

        check_rate_limit(
            db,
            key=f"identity:{identity}",
            maximum=10,
            period=900,
        )

        user = db.scalar(
            select(User).where(
                User.identity == identity
            )
        )

        stored_hash = (
            user.password_hash
            if user
            else DUMMY_HASH
        )

        valid_password = passwords.verify(
            payload.password.get_secret_value(),
            stored_hash,
        )

        if (
            not valid_password
            or not user
            or not user.active
            or (
                expected_role
                and user.role != expected_role
            )
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials or account access",
            )

        now = int(time.time())

        # Replace any current session.
        old_token = request.cookies.get(COOKIE_NAME)

        if old_token:
            db.execute(
                delete(LoginSession).where(
                    LoginSession.token_hash == digest(old_token)
                )
            )

        # Remove expired records.
        db.execute(
            delete(LoginSession).where(
                LoginSession.expires_at <= now
            )
        )

        db.execute(
            delete(LoginLimit).where(
                LoginLimit.expires_at <= now
            )
        )

        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)

        lifetime = settings.session_hours * 3600

        db.add(
            LoginSession(
                token_hash=digest(token),
                user_id=user.id,
                csrf_hash=digest(csrf_token),
                expires_at=now + lifetime,
            )
        )

        db.commit()

        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=lifetime,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            path="/",
        )

        destination = (
            "/admin/dashboard"
            if user.role == "admin"
            else "/dashboard"
        )

        return LoginResult(
            user=PublicUser.model_validate(user),
            redirect_to=destination,
            csrf_token=csrf_token,
        )

    # --------------------------------------------------
    # Login endpoints
    # --------------------------------------------------

    @app.post(
        "/api/v1/auth/register",
        response_model=PublicUser,
        status_code=201,
    )
    def register_account(
        payload: AccountCreate,
        db: Session = Depends(get_db),
    ):
        identity = payload.identity.strip().casefold()
        name = payload.name.strip()

        if not identity or not name:
            raise HTTPException(
                status_code=422,
                detail="Identity and name are required",
            )

        existing_user = db.scalar(
            select(User).where(User.identity == identity)
        )

        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="Account already exists",
            )

        user = User(
            identity=identity,
            name=name,
            role="user",
            password_hash=passwords.hash(
                payload.password.get_secret_value()
            ),
            active=True,
        )

        db.add(user)

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Account already exists",
            )

        db.refresh(user)
        return user

    @app.post(
        "/api/v1/auth/user/login",
        response_model=LoginResult,
    )
    def user_login(
        payload: Credentials,
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ):
        return perform_login(
            payload,
            request,
            response,
            db,
            expected_role="user",
        )

    @app.post(
        "/api/v1/auth/admin/login",
        response_model=LoginResult,
    )
    def admin_login(
        payload: Credentials,
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ):
        return perform_login(
            payload,
            request,
            response,
            db,
            expected_role="admin",
        )

    @app.post(
        "/api/v1/auth/login",
        response_model=LoginResult,
    )
    def shared_login(
        payload: Credentials,
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ):
        return perform_login(
            payload,
            request,
            response,
            db,
            expected_role=None,
        )

    # --------------------------------------------------
    # Current account
    # --------------------------------------------------

    @app.get(
        "/api/v1/me",
        response_model=PublicUser,
    )
    def me(
        user: User = Depends(get_current_user),
    ):
        return user

    # --------------------------------------------------
    # CSRF token
    # --------------------------------------------------

    @app.get("/api/v1/auth/csrf")
    def refresh_csrf(
        auth=Depends(get_current_session),
        db: Session = Depends(get_db),
    ):
        token = secrets.token_urlsafe(32)

        db.execute(
            update(LoginSession)
            .where(
                LoginSession.token_hash == auth[0].token_hash
            )
            .values(
                csrf_hash=digest(token)
            )
        )

        db.commit()

        return {
            "csrf_token": token
        }

    # --------------------------------------------------
    # Logout
    # --------------------------------------------------

    @app.post(
        "/api/v1/auth/logout",
        status_code=204,
    )
    def logout(
        request: Request,
        response: Response,
        auth=Depends(get_current_session),
        db: Session = Depends(get_db),
    ):
        csrf_token = request.headers.get(
            "X-CSRF-Token",
            "",
        )

        valid_csrf = (
            csrf_token
            and secrets.compare_digest(
                digest(csrf_token),
                auth[0].csrf_hash,
            )
        )

        if not valid_csrf:
            raise HTTPException(
                status_code=403,
                detail="Invalid CSRF token",
            )

        db.execute(
            delete(LoginSession).where(
                LoginSession.token_hash == auth[0].token_hash
            )
        )

        db.commit()

        response.delete_cookie(
            key=COOKIE_NAME,
            path="/",
            secure=settings.cookie_secure,
            httponly=True,
            samesite="lax",
        )

    # --------------------------------------------------
    # Protected route examples
    # --------------------------------------------------

    @app.get("/api/v1/admin/dashboard")
    def admin_dashboard(
        user: User = Depends(require_admin),
    ):
        return {
            "message": "Admin authentication verified",
            "name": user.name,
        }

    @app.get("/api/v1/user/dashboard")
    def user_dashboard(
        user: User = Depends(require_user),
    ):
        return {
            "message": "Employee authentication verified",
            "name": user.name,
        }

    @app.get("/health")
    def health():
        return {
            "status": "ok"
        }

    return app


app = create_app()