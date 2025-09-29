import enum
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    Boolean,
    ForeignKey,
    Text,
    DateTime,
    Date,
    UniqueConstraint,
    Float,
)
from sqlalchemy.orm import relationship

from .database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    professional = "professional"
    client = "client"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.client, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    primary_professional_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    professional_clients = relationship(
        "User",
        back_populates="primary_professional",
        foreign_keys="User.primary_professional_id",
    )
    primary_professional = relationship(
        "User",
        back_populates="professional_clients",
        remote_side=[id],
        foreign_keys=[primary_professional_id],
    )

    subscriptions = relationship("Subscription", back_populates="professional", foreign_keys="Subscription.professional_id")
    created_assignments = relationship("Assignment", back_populates="professional", foreign_keys="Assignment.professional_id")
    client_assignments = relationship("Assignment", back_populates="client", foreign_keys="Assignment.client_id")


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, default=0)
    duration_days = Column(Integer, default=30)
    features = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    subscriptions = relationship("Subscription", back_populates="plan")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    professional_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False)
    start_date = Column(Date, default=date.today)
    end_date = Column(Date, nullable=True)
    status = Column(String, default="active")

    professional = relationship("User", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)

    questions = relationship("AssessmentQuestion", back_populates="assessment", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="assessment")


class QuestionType(str, enum.Enum):
    single_choice = "single_choice"
    multiple_choice = "multiple_choice"


class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=False)
    text = Column(Text, nullable=False)
    type = Column(Enum(QuestionType), default=QuestionType.single_choice)
    order = Column(Integer, default=0)

    assessment = relationship("Assessment", back_populates="questions")
    options = relationship("AssessmentOption", back_populates="question", cascade="all, delete-orphan")


class AssessmentOption(Base):
    __tablename__ = "assessment_options"
    __table_args__ = (UniqueConstraint("question_id", "text", name="uq_question_option"),)

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("assessment_questions.id"), nullable=False)
    text = Column(Text, nullable=False)
    value = Column(Integer, default=0)

    question = relationship("AssessmentQuestion", back_populates="options")


class AssignmentStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    archived = "archived"


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=False)
    professional_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    access_token = Column(String, unique=True, nullable=False, index=True)
    status = Column(Enum(AssignmentStatus), default=AssignmentStatus.pending)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    assessment = relationship("Assessment", back_populates="assignments")
    professional = relationship("User", back_populates="created_assignments", foreign_keys=[professional_id])
    client = relationship("User", back_populates="client_assignments", foreign_keys=[client_id])
    responses = relationship("AssignmentResponse", back_populates="assignment", cascade="all, delete-orphan")
    result = relationship("AssignmentResult", back_populates="assignment", uselist=False, cascade="all, delete-orphan")
    conclusion = relationship("AssignmentConclusion", back_populates="assignment", uselist=False, cascade="all, delete-orphan")


class AssignmentResponse(Base):
    __tablename__ = "assignment_responses"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("assessment_questions.id"), nullable=False)
    option_id = Column(Integer, ForeignKey("assessment_options.id"), nullable=True)
    value = Column(Integer, default=0)

    assignment = relationship("Assignment", back_populates="responses")
    question = relationship("AssessmentQuestion")
    option = relationship("AssessmentOption")


class AssignmentResult(Base):
    __tablename__ = "assignment_results"

    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), unique=True)
    total_score = Column(Integer, default=0)
    summary = Column(Text, nullable=True)

    assignment = relationship("Assignment", back_populates="result")


class AssignmentConclusion(Base):
    __tablename__ = "assignment_conclusions"

    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), unique=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    assignment = relationship("Assignment", back_populates="conclusion")
    author = relationship("User")
