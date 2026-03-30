from __future__ import annotations
"""
users/repository.py - UserRepository 인터페이스 + Mock/PG 구현체
USE_MOCK_DB=true  → MockUserRepository (개발/테스트)
USE_MOCK_DB=false → PGUserRepository   (운영)
"""
from abc import ABC, abstractmethod

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.users.models import Base, User


# ── 인터페이스 ─────────────────────────────────────────────────────
class UserRepository(ABC):
    @abstractmethod
    def get_user_by_knox_id(self, knox_id: str) -> dict | None:
        pass

    @abstractmethod
    def get_all_users(self) -> list[dict]:
        pass


# ── Mock 구현체 ────────────────────────────────────────────────────
MOCK_USERS: list[dict] = [
    {"knox_id": "jyd1234", "name": "장영동", "team": "AI팀",  "eng_name": "Youngdong Jang"},
    {"knox_id": "kim5678", "name": "김철수", "team": "개발팀", "eng_name": "Chulsoo Kim"},
]


class MockUserRepository(UserRepository):
    def get_user_by_knox_id(self, knox_id: str) -> dict | None:
        return next((u for u in MOCK_USERS if u["knox_id"] == knox_id), None)

    def get_all_users(self) -> list[dict]:
        return MOCK_USERS


# ── PostgreSQL 구현체 ──────────────────────────────────────────────
class PGUserRepository(UserRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_knox_id(self, knox_id: str) -> dict | None:
        user = self.db.query(User).filter_by(knox_id=knox_id).first()
        return user.to_dict() if user else None

    def get_all_users(self) -> list[dict]:
        return [u.to_dict() for u in self.db.query(User).all()]


# ── 팩토리 함수 ────────────────────────────────────────────────────
def get_user_repository(use_mock: bool = True, db: Session | None = None) -> UserRepository:
    if use_mock:
        return MockUserRepository()
    if db is None:
        raise ValueError("PGUserRepository requires a SQLAlchemy Session (db=...)")
    return PGUserRepository(db)


def create_pg_session_factory(database_url: str):
    """운영 환경에서 사용하는 SQLAlchemy 세션 팩토리를 반환한다."""
    engine = create_engine(database_url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
