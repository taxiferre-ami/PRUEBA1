from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, Boolean, Enum
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import enum
import os

Base = declarative_base()

class StatusEnum(str, enum.Enum):
    preparing = "preparando"
    drawn = "sorteado"
    canceled = "cancelado"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    full_name = Column(String, nullable=False)
    phone = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    alias = Column(String, nullable=True)
    needs = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    code = Column(String(8), unique=True, index=True, nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id"))
    status = Column(Enum(StatusEnum), default=StatusEnum.preparing)
    created_at = Column(DateTime, default=datetime.utcnow)
    creator = relationship("User")
    participants = relationship("EventParticipant", back_populates="event", cascade="all, delete-orphan")
    exclusions = relationship("Exclusion", back_populates="event", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="event", cascade="all, delete-orphan")

class EventParticipant(Base):
    __tablename__ = "event_participants"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    event = relationship("Event", back_populates="participants")
    user = relationship("User")

class Exclusion(Base):
    __tablename__ = "exclusions"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    giver_id = Column(Integer, ForeignKey("users.id"))
    receiver_id = Column(Integer, ForeignKey("users.id"))
    mutual = Column(Boolean, default=False)
    event = relationship("Event", back_populates="exclusions")

class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    giver_id = Column(Integer, ForeignKey("users.id"))
    receiver_id = Column(Integer, ForeignKey("users.id"))
    private_code = Column(String, unique=True, index=True)
    event = relationship("Event", back_populates="assignments")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./amigo.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
