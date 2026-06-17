"""SQLAlchemy declarative base shared by all ORM table models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared base class for all database table models.

    Subclasses are used for schema discovery, Alembic autogeneration, and
    runtime data access via SQLAlchemy async sessions.
    """
