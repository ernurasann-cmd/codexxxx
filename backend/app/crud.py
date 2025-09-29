from datetime import date, datetime, timedelta
import secrets
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .models import (
    Assignment,
    AssignmentConclusion,
    AssignmentResponse,
    AssignmentResult,
    AssignmentStatus,
    Assessment,
    AssessmentOption,
    AssessmentQuestion,
    Subscription,
    SubscriptionPlan,
    User,
    UserRole,
)
from .security import get_password_hash


# User operations

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def count_admins(db: Session) -> int:
    return db.query(User).filter(User.role == UserRole.admin).count()


def create_user(db: Session, *, email: str, full_name: str, password: str, role: UserRole, primary_professional_id: Optional[int] = None) -> User:
    if get_user_by_email(db, email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    if role == UserRole.client and primary_professional_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client must be assigned to a professional")
    hashed_password = get_password_hash(password)
    user = User(
        email=email,
        full_name=full_name,
        hashed_password=hashed_password,
        role=role,
        primary_professional_id=primary_professional_id if role == UserRole.client else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: User, *, full_name: Optional[str] = None, password: Optional[str] = None, is_active: Optional[bool] = None) -> User:
    if full_name:
        user.full_name = full_name
    if password:
        user.hashed_password = get_password_hash(password)
    if is_active is not None:
        user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


# Subscription operations

def create_subscription_plan(
    db: Session,
    *,
    name: str,
    description: Optional[str],
    price: float,
    duration_days: int,
    features: Optional[str],
) -> SubscriptionPlan:
    plan = SubscriptionPlan(
        name=name,
        description=description,
        price=price,
        duration_days=duration_days,
        features=features,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def list_subscription_plans(db: Session) -> List[SubscriptionPlan]:
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active == True).all()


def assign_subscription(
    db: Session,
    *,
    professional: User,
    plan: SubscriptionPlan,
) -> Subscription:
    if professional.role != UserRole.professional:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only professionals can have subscriptions")
    start_date = date.today()
    end_date = start_date + timedelta(days=plan.duration_days)
    subscription = Subscription(
        professional=professional,
        plan=plan,
        start_date=start_date,
        end_date=end_date,
        status="active",
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def is_subscription_active(professional: User) -> bool:
    active_subscriptions = [
        sub
        for sub in professional.subscriptions
        if sub.status == "active" and (sub.end_date is None or sub.end_date >= date.today())
    ]
    return bool(active_subscriptions)


# Assessment operations

def create_assessment(db: Session, *, title: str, description: Optional[str], created_by_id: Optional[int], questions_data: List[dict]) -> Assessment:
    assessment = Assessment(title=title, description=description, created_by_id=created_by_id)
    for idx, question in enumerate(questions_data):
        q = AssessmentQuestion(
            text=question["text"],
            type=question.get("type"),
            order=question.get("order", idx),
        )
        for option in question["options"]:
            q.options.append(
                AssessmentOption(
                    text=option["text"],
                    value=option.get("value", 0),
                )
            )
        assessment.questions.append(q)
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


def list_assessments(db: Session) -> List[Assessment]:
    return db.query(Assessment).filter(Assessment.is_active == True).all()


def get_assessment(db: Session, assessment_id: int) -> Assessment:
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    return assessment


# Assignment operations

def create_assignment(db: Session, *, assessment: Assessment, professional: User, client: User) -> Assignment:
    if client.primary_professional_id != professional.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client is not linked to this professional")
    access_token = secrets.token_urlsafe(16)
    assignment = Assignment(
        assessment=assessment,
        professional=professional,
        client=client,
        access_token=access_token,
        status=AssignmentStatus.pending,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def get_assignment(db: Session, assignment_id: int) -> Assignment:
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return assignment


def get_assignment_by_token(db: Session, token: str) -> Assignment:
    assignment = db.query(Assignment).filter(Assignment.access_token == token).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return assignment


def submit_assignment(db: Session, *, assignment: Assignment, answers: List[dict]) -> AssignmentResult:
    assignment.responses.clear()
    total_score = 0
    for answer in answers:
        question_id = answer["question_id"]
        option_id = answer.get("option_id")
        value = answer.get("value")
        option_value = 0
        if option_id:
            option = (
                db.query(AssessmentOption)
                .join(AssessmentQuestion)
                .filter(AssessmentOption.id == option_id, AssessmentQuestion.assessment_id == assignment.assessment_id)
                .first()
            )
            if not option:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid option selected")
            option_value = option.value
        elif value is not None:
            option_value = int(value)
        response = AssignmentResponse(
            question_id=question_id,
            option_id=option_id,
            value=option_value,
        )
        total_score += option_value
        assignment.responses.append(response)
    summary = f"Total score: {total_score}"
    if assignment.result:
        assignment.result.total_score = total_score
        assignment.result.summary = summary
    else:
        assignment.result = AssignmentResult(total_score=total_score, summary=summary)
    assignment.status = AssignmentStatus.completed
    assignment.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(assignment)
    return assignment.result


def set_assignment_status(db: Session, *, assignment: Assignment, status: AssignmentStatus) -> Assignment:
    assignment.status = status
    if status == AssignmentStatus.archived and assignment.completed_at is None:
        assignment.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(assignment)
    return assignment


def add_conclusion(db: Session, *, assignment: Assignment, author: User, content: str) -> AssignmentConclusion:
    if assignment.professional_id != author.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot add conclusion for another professional's assignment")
    if assignment.conclusion:
        assignment.conclusion.content = content
        assignment.conclusion.created_at = datetime.utcnow()
    else:
        assignment.conclusion = AssignmentConclusion(author=author, content=content)
    db.commit()
    db.refresh(assignment)
    return assignment.conclusion
