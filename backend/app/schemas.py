from datetime import datetime, date
from typing import List, Optional

from pydantic import BaseModel, EmailStr

from .models import AssignmentStatus, QuestionType, UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int
    role: UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool

    class Config:
        orm_mode = True


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: UserRole
    primary_professional_id: Optional[int] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


class UserRead(UserBase):
    id: int
    created_at: datetime
    primary_professional_id: Optional[int]


class SubscriptionPlanBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    duration_days: int
    features: Optional[str] = None
    is_active: bool = True


class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass


class SubscriptionPlanRead(SubscriptionPlanBase):
    id: int

    class Config:
        orm_mode = True


class SubscriptionBase(BaseModel):
    professional_id: int
    plan_id: int
    start_date: date
    end_date: Optional[date]
    status: str


class SubscriptionRead(SubscriptionBase):
    id: int
    plan: SubscriptionPlanRead

    class Config:
        orm_mode = True


class AssessmentOptionBase(BaseModel):
    text: str
    value: int


class AssessmentOptionCreate(AssessmentOptionBase):
    pass


class AssessmentOptionRead(AssessmentOptionBase):
    id: int

    class Config:
        orm_mode = True


class AssessmentQuestionBase(BaseModel):
    text: str
    type: QuestionType = QuestionType.single_choice
    order: int = 0


class AssessmentQuestionCreate(AssessmentQuestionBase):
    options: List[AssessmentOptionCreate]


class AssessmentQuestionRead(AssessmentQuestionBase):
    id: int
    options: List[AssessmentOptionRead]

    class Config:
        orm_mode = True


class AssessmentBase(BaseModel):
    title: str
    description: Optional[str] = None
    is_active: bool = True


class AssessmentCreate(AssessmentBase):
    questions: List[AssessmentQuestionCreate]


class AssessmentRead(AssessmentBase):
    id: int
    questions: List[AssessmentQuestionRead]

    class Config:
        orm_mode = True


class AssignmentBase(BaseModel):
    assessment_id: int
    client_id: int


class AssignmentCreate(AssignmentBase):
    pass


class AssignmentRead(BaseModel):
    id: int
    assessment: AssessmentRead
    professional_id: int
    client_id: int
    access_token: str
    status: AssignmentStatus
    created_at: datetime
    completed_at: Optional[datetime]
    result: Optional["AssignmentResultRead"] = None
    conclusion: Optional["ConclusionRead"] = None

    class Config:
        orm_mode = True


class AnswerOption(BaseModel):
    question_id: int
    option_id: Optional[int]
    value: Optional[int] = None


class AssignmentSubmission(BaseModel):
    answers: List[AnswerOption]


class AssignmentResultRead(BaseModel):
    id: Optional[int]
    total_score: int
    summary: Optional[str]

    class Config:
        orm_mode = True


class ConclusionCreate(BaseModel):
    content: str


class ConclusionRead(BaseModel):
    id: Optional[int]
    content: str
    author_id: int
    created_at: datetime

    class Config:
        orm_mode = True


AssignmentRead.update_forward_refs()
