"""
Database Configuration — SQLAlchemy + Cloud SQL (PostgreSQL) for production,
SQLite for local development.

Connection strategy:
  1. CLOUD_SQL_CONNECTION_NAME set  → Cloud SQL Python Connector (IAM, no TCP needed)
  2. DATABASE_URL starts postgres   → direct TCP PostgreSQL
  3. Fallback                       → SQLite at /tmp/productivity.db
"""

import os
import logging
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

logger = logging.getLogger(__name__)

CLOUD_SQL_CONNECTION_NAME = os.getenv("CLOUD_SQL_CONNECTION_NAME", "")
DATABASE_URL               = os.getenv("DATABASE_URL", "")
DB_USER                    = os.getenv("DB_USER", "postgres")
DB_PASSWORD                = os.getenv("DB_PASSWORD", "")
DB_NAME                    = os.getenv("DB_NAME", "orchestra")


def _build_engine():
    # ── 1. Cloud SQL Python Connector ────────────────────────────────────────
    if CLOUD_SQL_CONNECTION_NAME:
        try:
            from google.cloud.sql.connector import Connector, IPTypes
            import pg8000
            connector = Connector()

            def _get_conn():
                return connector.connect(
                    CLOUD_SQL_CONNECTION_NAME,
                    "pg8000",
                    user=DB_USER,
                    password=DB_PASSWORD,
                    db=DB_NAME,
                    ip_type=IPTypes.PRIVATE if os.getenv("PRIVATE_IP") else IPTypes.PUBLIC,
                )

            eng = create_engine(
                "postgresql+pg8000://",
                creator=_get_conn,
                poolclass=QueuePool,
                pool_size=1, max_overflow=2,
                pool_timeout=30, pool_recycle=1800,
                pool_pre_ping=True, echo=False,
            )
            logger.info(f"✅ Cloud SQL connector: {CLOUD_SQL_CONNECTION_NAME}")
            return eng
        except Exception as e:
            logger.error(f"❌ Cloud SQL connector failed ({e}), trying next method")

    # ── 2. Direct PostgreSQL TCP ──────────────────────────────────────────────
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        url = DATABASE_URL\
            .replace("postgresql://", "postgresql+pg8000://", 1)\
            .replace("postgres://", "postgresql+pg8000://", 1)
        eng = create_engine(
            url,
            poolclass=QueuePool,
            pool_size=1, max_overflow=2,
            pool_timeout=30, pool_recycle=1800,
            pool_pre_ping=True, echo=False,
        )
        logger.info("✅ PostgreSQL TCP engine")
        return eng

    # ── 3. SQLite (local dev / temporary fallback) ────────────────────────────
    sqlite_url = DATABASE_URL if (DATABASE_URL and "sqlite" in DATABASE_URL) \
                              else "sqlite:////tmp/productivity.db"
    eng = create_engine(
        sqlite_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool, echo=False,
    )
    logger.warning(f"⚠️  SQLite fallback: {sqlite_url}  (data is NOT permanent on Cloud Run)")
    return eng


# ── Engine & Session Initialization ──────────────────────────────────────────
_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine

def get_session():
    engine = get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

Base = declarative_base()


# ============================================================================
# MODELS
# ============================================================================

class Task(Base):
    __tablename__ = "tasks"
    id           = Column(Integer,     primary_key=True, index=True)
    task_id      = Column(String(32),  unique=True, index=True, nullable=False)
    title        = Column(String(255), index=True,  nullable=False)
    description  = Column(Text,        nullable=True)
    priority     = Column(String(20),  default="medium")
    status       = Column(String(20),  default="open")
    due_date     = Column(DateTime,    nullable=True)
    created_at   = Column(DateTime,    default=datetime.utcnow, index=True)
    updated_at   = Column(DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime,    nullable=True)
    subtasks     = Column(Integer,     default=0)
    dependencies = Column(Text,        nullable=True)
    assigned_to  = Column(String(255), nullable=True)
    custom_data  = Column(Text,        nullable=True)
    source       = Column(String(50),  nullable=True)


class Note(Base):
    __tablename__ = "notes"
    id          = Column(Integer,     primary_key=True, index=True)
    note_id     = Column(String(32),  unique=True, index=True, nullable=False)
    title       = Column(String(255), index=True,  nullable=False)
    content     = Column(Text,        nullable=False)
    category    = Column(String(100), nullable=True, index=True)
    tags        = Column(Text,        nullable=True)
    is_pinned   = Column(Boolean,     default=False)
    is_archived = Column(Boolean,     default=False)
    created_at  = Column(DateTime,    default=datetime.utcnow, index=True)
    updated_at  = Column(DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by  = Column(String(255), nullable=True)
    custom_data = Column(Text,        nullable=True)


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    id               = Column(Integer,     primary_key=True, index=True)
    event_id         = Column(String(32),  unique=True, index=True, nullable=False)
    title            = Column(String(255), index=True,  nullable=False)
    description      = Column(Text,        nullable=True)
    start_time       = Column(DateTime,    index=True)
    end_time         = Column(DateTime,    index=True)
    location         = Column(String(255), nullable=True)
    duration_minutes = Column(Integer,     default=60)
    status           = Column(String(20),  default="scheduled")
    attendees        = Column(Text,        nullable=True)
    organizer        = Column(String(255), nullable=True)
    is_all_day       = Column(Boolean,     default=False)
    is_recurring     = Column(Boolean,     default=False)
    recurrence_rule  = Column(String(255), nullable=True)
    color            = Column(String(10),  nullable=True)
    created_at       = Column(DateTime,    default=datetime.utcnow, index=True)
    updated_at       = Column(DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by       = Column(String(255), nullable=True)
    custom_data      = Column(Text,        nullable=True)
    source           = Column(String(50),  nullable=True)


class WorkflowHistory(Base):
    """Persists every orchestration run for audit and history."""
    __tablename__ = "workflow_history"
    id             = Column(Integer,    primary_key=True, index=True)
    workflow_id    = Column(String(32), unique=True, index=True, nullable=False)
    goal           = Column(Text,       nullable=False)
    priority       = Column(String(20), default="medium")
    status         = Column(String(20), default="completed")
    steps_count    = Column(Integer,    default=0)
    tasks_created  = Column(Integer,    default=0)
    events_created = Column(Integer,    default=0)
    source         = Column(String(50), nullable=True)
    created_at     = Column(DateTime,   default=datetime.utcnow, index=True)
    completed_at   = Column(DateTime,   nullable=True)
    error          = Column(Text,       nullable=True)


class Book(Base):
    __tablename__ = "books"
    id           = Column(Integer,     primary_key=True, index=True)
    book_id      = Column(String(32),  unique=True, index=True, nullable=False)
    title        = Column(String(255), index=True,  nullable=False)
    author       = Column(String(255), index=True,  nullable=True)
    status       = Column(String(20),  default="to-read") # to-read, in-progress, completed
    current_page = Column(Integer,     default=0)
    total_pages  = Column(Integer,     default=1)
    created_at   = Column(DateTime,    default=datetime.utcnow, index=True)
    updated_at   = Column(DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)
    finished_at  = Column(DateTime,    nullable=True)


# ============================================================================
# INIT
# ============================================================================

def init_db():
    try:
        Base.metadata.create_all(bind=get_engine())
        logger.info("✅ Database schema ready")
    except Exception as e:
        logger.error(f"❌ init_db failed: {e}")
        raise


def get_db_session():
    db = get_session()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# TASKS
# ============================================================================

def create_task_in_db(task_id, title, description=None, priority="medium",
                      due_date=None, subtasks=0, dependencies=None, source="manual"):
    db = get_session()
    try:
        t = Task(task_id=task_id, title=title, description=description,
                 priority=priority, due_date=due_date, subtasks=subtasks,
                 dependencies=dependencies, source=source)
        db.add(t); db.commit(); db.refresh(t)
        return t
    except Exception as e:
        db.rollback(); logger.error(f"❌ create_task_in_db: {e}"); raise
    finally:
        db.close()


def get_all_tasks(limit=100, offset=0, status=None):
    db = get_session()
    try:
        q = db.query(Task)
        if status:
            q = q.filter(Task.status == status)
        return q.order_by(Task.created_at.desc()).limit(limit).offset(offset).all()
    finally:
        db.close()


def get_task_by_id(task_id):
    db = get_session()
    try:
        return db.query(Task).filter(Task.task_id == task_id).first()
    finally:
        db.close()


def update_task(task_id, **kwargs):
    db = get_session()
    try:
        t = db.query(Task).filter(Task.task_id == task_id).first()
        if t:
            for k, v in kwargs.items():
                if hasattr(t, k): setattr(t, k, v)
            t.updated_at = datetime.utcnow()
            db.commit()
        return t
    except Exception as e:
        db.rollback(); raise
    finally:
        db.close()


def delete_task(task_id):
    db = get_session()
    try:
        t = db.query(Task).filter(Task.task_id == task_id).first()
        if t: db.delete(t); db.commit(); return True
        return False
    except Exception as e:
        db.rollback(); raise
    finally:
        db.close()


# ============================================================================
# NOTES
# ============================================================================

def create_note_in_db(note_id, title, content, category=None, tags=None):
    db = get_session()
    try:
        n = Note(note_id=note_id, title=title, content=content,
                 category=category, tags=tags)
        db.add(n); db.commit(); db.refresh(n)
        return n
    except Exception as e:
        db.rollback(); raise
    finally:
        db.close()


def get_all_notes(limit=100, offset=0, category=None):
    db = get_session()
    try:
        q = db.query(Note).filter(Note.is_archived == False)
        if category: q = q.filter(Note.category == category)
        return q.order_by(Note.created_at.desc()).limit(limit).offset(offset).all()
    finally:
        db.close()


def get_note_by_id(note_id):
    db = get_session()
    try:
        return db.query(Note).filter(Note.note_id == note_id).first()
    finally:
        db.close()


def update_note(note_id, **kwargs):
    db = get_session()
    try:
        n = db.query(Note).filter(Note.note_id == note_id).first()
        if n:
            for k, v in kwargs.items():
                if hasattr(n, k): setattr(n, k, v)
            n.updated_at = datetime.utcnow()
            db.commit()
        return n
    except Exception as e:
        db.rollback(); raise
    finally:
        db.close()


def search_notes(search_query, limit=50):
    db = get_session()
    try:
        return db.query(Note).filter(
            (Note.title.ilike(f"%{search_query}%") |
             Note.content.ilike(f"%{search_query}%")) &
            (Note.is_archived == False)
        ).limit(limit).all()
    finally:
        db.close()


# ============================================================================
# CALENDAR EVENTS
# ============================================================================

def create_event_in_db(event_id, title, start_time, end_time,
                       location=None, duration_minutes=60,
                       attendees=None, description=None, source="manual"):
    db = get_session()
    try:
        e = CalendarEvent(event_id=event_id, title=title,
                          start_time=start_time, end_time=end_time,
                          location=location, duration_minutes=duration_minutes,
                          attendees=attendees, description=description, source=source)
        db.add(e); db.commit(); db.refresh(e)
        return e
    except Exception as e:
        db.rollback(); raise
    finally:
        db.close()


def get_all_events(limit=100, offset=0, upcoming_only=False):
    db = get_session()
    try:
        q = db.query(CalendarEvent)
        if upcoming_only:
            q = q.filter(CalendarEvent.start_time >= datetime.utcnow())
        return q.order_by(CalendarEvent.start_time.asc()).limit(limit).offset(offset).all()
    finally:
        db.close()


def get_event_by_id(event_id):
    db = get_session()
    try:
        return db.query(CalendarEvent).filter(CalendarEvent.event_id == event_id).first()
    finally:
        db.close()


def get_upcoming_events(days_ahead=7):
    from datetime import timedelta
    db = get_session()
    try:
        now = datetime.utcnow()
        return db.query(CalendarEvent).filter(
            CalendarEvent.start_time >= now,
            CalendarEvent.start_time <= now + timedelta(days=days_ahead)
        ).order_by(CalendarEvent.start_time.asc()).all()
    finally:
        db.close()


def update_event(event_id, **kwargs):
    db = get_session()
    try:
        ev = db.query(CalendarEvent).filter(CalendarEvent.event_id == event_id).first()
        if ev:
            for k, v in kwargs.items():
                if hasattr(ev, k): setattr(ev, k, v)
            ev.updated_at = datetime.utcnow()
            db.commit()
        return ev
    except Exception as e:
        db.rollback(); raise
    finally:
        db.close()


# ============================================================================
# WORKFLOW HISTORY
# ============================================================================

def save_workflow_history(workflow_id, goal, priority="medium", steps_count=0,
                          tasks_created=0, events_created=0, source="text",
                          status="completed", error=None):
    db = get_session()
    try:
        wf = WorkflowHistory(
            workflow_id=workflow_id, goal=goal, priority=priority,
            steps_count=steps_count, tasks_created=tasks_created,
            events_created=events_created, source=source, status=status,
            error=error,
            completed_at=datetime.utcnow() if status != "running" else None,
        )
        db.add(wf); db.commit()
        return wf
    except Exception as e:
        db.rollback(); logger.warning(f"Workflow history save failed: {e}")
    finally:
        db.close()


def get_workflow_history(limit=50):
    db = get_session()
    try:
        return db.query(WorkflowHistory)\
                 .order_by(WorkflowHistory.created_at.desc())\
                 .limit(limit).all()
    finally:
        db.close()


# ============================================================================
# BOOKS (ALEXANDRIA)
# ============================================================================

def create_book_in_db(book_id, title, author=None, status="to-read", total_pages=1):
    db = get_session()
    try:
        b = Book(book_id=book_id, title=title, author=author, status=status, total_pages=total_pages)
        db.add(b); db.commit(); db.refresh(b)
        return b
    except Exception as e:
        db.rollback(); raise
    finally:
        db.close()


def get_all_books(limit=100, status=None):
    db = get_session()
    try:
        q = db.query(Book)
        if status: q = q.filter(Book.status == status)
        return q.order_by(Book.updated_at.desc()).limit(limit).all()
    finally:
        db.close()


def update_book_progress(book_id, current_page, status=None):
    db = get_session()
    try:
        b = db.query(Book).filter(Book.book_id == book_id).first()
        if b:
            b.current_page = current_page
            if status: b.status = status
            if status == "completed": b.finished_at = datetime.utcnow()
            b.updated_at = datetime.utcnow()
            db.commit()
        return b
    except Exception as e:
        db.rollback(); raise
    finally:
        db.close()
