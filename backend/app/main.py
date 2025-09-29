from datetime import timedelta
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .config import settings
from .database import Base, engine, get_db
from .deps import (
    get_current_active_admin,
    get_current_active_client,
    get_current_active_professional,
    get_current_active_user,
)
from .pdf import build_assignment_pdf
from .security import create_access_token, verify_password

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.post("/auth/token", response_model=schemas.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> schemas.Token:
    user = crud.get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    access_token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return schemas.Token(access_token=access_token)


@app.post("/auth/register", response_model=schemas.UserRead)
def register_first_admin(user_in: schemas.UserCreate, db: Session = Depends(get_db)) -> schemas.UserRead:
    if crud.count_admins(db) > 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration closed. Ask administrator to add users")
    if user_in.role != models.UserRole.admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="First user must be admin")
    user = crud.create_user(
        db,
        email=user_in.email,
        full_name=user_in.full_name,
        password=user_in.password,
        role=user_in.role,
    )
    return user


@app.get("/users/me", response_model=schemas.UserRead)
def read_users_me(current_user: models.User = Depends(get_current_active_user)) -> models.User:
    return current_user


@app.post("/admin/users", response_model=schemas.UserRead)
def admin_create_user(
    user_in: schemas.UserCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_active_admin),
) -> schemas.UserRead:
    user = crud.create_user(
        db,
        email=user_in.email,
        full_name=user_in.full_name,
        password=user_in.password,
        role=user_in.role,
        primary_professional_id=user_in.primary_professional_id,
    )
    return user


@app.get("/admin/users", response_model=List[schemas.UserRead])
def admin_list_users(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_active_admin),
) -> List[schemas.UserRead]:
    return db.query(models.User).all()


@app.post("/admin/subscription-plans", response_model=schemas.SubscriptionPlanRead)
def create_plan(
    plan_in: schemas.SubscriptionPlanCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_active_admin),
) -> schemas.SubscriptionPlanRead:
    plan = crud.create_subscription_plan(
        db,
        name=plan_in.name,
        description=plan_in.description,
        price=plan_in.price,
        duration_days=plan_in.duration_days,
        features=plan_in.features,
    )
    return plan


@app.get("/admin/subscription-plans", response_model=List[schemas.SubscriptionPlanRead])
def list_plans(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_active_admin),
) -> List[schemas.SubscriptionPlanRead]:
    return crud.list_subscription_plans(db)


@app.post("/admin/subscriptions", response_model=schemas.SubscriptionRead)
def assign_plan(
    professional_id: int,
    plan_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_active_admin),
) -> schemas.SubscriptionRead:
    professional = db.query(models.User).filter(models.User.id == professional_id).first()
    if not professional:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Professional not found")
    plan = db.query(models.SubscriptionPlan).filter(models.SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    subscription = crud.assign_subscription(db, professional=professional, plan=plan)
    return subscription


@app.get("/admin/assignments", response_model=List[schemas.AssignmentRead])
def admin_list_assignments(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_active_admin),
) -> List[schemas.AssignmentRead]:
    return db.query(models.Assignment).all()


@app.post("/admin/assessments", response_model=schemas.AssessmentRead)
def admin_create_assessment(
    assessment_in: schemas.AssessmentCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_active_admin),
) -> schemas.AssessmentRead:
    assessment = crud.create_assessment(
        db,
        title=assessment_in.title,
        description=assessment_in.description,
        created_by_id=current_admin.id,
        questions_data=[question.dict() for question in assessment_in.questions],
    )
    return assessment


@app.get("/assessments", response_model=List[schemas.AssessmentRead])
def public_list_assessments(db: Session = Depends(get_db)) -> List[schemas.AssessmentRead]:
    return crud.list_assessments(db)


@app.get("/professional/clients", response_model=List[schemas.UserRead])
def professional_clients(
    current_user: models.User = Depends(get_current_active_professional),
    db: Session = Depends(get_db),
) -> List[schemas.UserRead]:
    return (
        db.query(models.User)
        .filter(models.User.primary_professional_id == current_user.id)
        .order_by(models.User.full_name)
        .all()
    )


@app.post("/professional/clients", response_model=schemas.UserRead)
def professional_create_client(
    client_in: schemas.UserCreate,
    current_user: models.User = Depends(get_current_active_professional),
    db: Session = Depends(get_db),
) -> schemas.UserRead:
    if client_in.role != models.UserRole.client:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only create clients")
    user = crud.create_user(
        db,
        email=client_in.email,
        full_name=client_in.full_name,
        password=client_in.password,
        role=models.UserRole.client,
        primary_professional_id=current_user.id,
    )
    return user


@app.get("/professional/assessments", response_model=List[schemas.AssessmentRead])
def professional_list_assessments(
    _: models.User = Depends(get_current_active_professional),
    db: Session = Depends(get_db),
) -> List[schemas.AssessmentRead]:
    return crud.list_assessments(db)


@app.post("/professional/assignments", response_model=schemas.AssignmentRead)
def professional_create_assignment(
    assignment_in: schemas.AssignmentCreate,
    current_user: models.User = Depends(get_current_active_professional),
    db: Session = Depends(get_db),
) -> schemas.AssignmentRead:
    if not crud.is_subscription_active(current_user):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Active subscription required")
    assessment = crud.get_assessment(db, assignment_in.assessment_id)
    client = db.query(models.User).filter(models.User.id == assignment_in.client_id).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    assignment = crud.create_assignment(db, assessment=assessment, professional=current_user, client=client)
    return assignment


@app.get("/professional/assignments", response_model=List[schemas.AssignmentRead])
def professional_list_assignments(
    current_user: models.User = Depends(get_current_active_professional),
    db: Session = Depends(get_db),
) -> List[schemas.AssignmentRead]:
    return (
        db.query(models.Assignment)
        .filter(models.Assignment.professional_id == current_user.id)
        .all()
    )


@app.post("/professional/assignments/{assignment_id}/archive", response_model=schemas.AssignmentRead)
def professional_archive_assignment(
    assignment_id: int,
    current_user: models.User = Depends(get_current_active_professional),
    db: Session = Depends(get_db),
) -> schemas.AssignmentRead:
    assignment = crud.get_assignment(db, assignment_id)
    if assignment.professional_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot archive another professional's assignment")
    assignment = crud.set_assignment_status(db, assignment=assignment, status=models.AssignmentStatus.archived)
    return assignment


@app.post("/professional/assignments/{assignment_id}/conclusion", response_model=schemas.ConclusionRead)
def professional_add_conclusion(
    assignment_id: int,
    conclusion: schemas.ConclusionCreate,
    current_user: models.User = Depends(get_current_active_professional),
    db: Session = Depends(get_db),
) -> schemas.ConclusionRead:
    assignment = crud.get_assignment(db, assignment_id)
    if assignment.professional_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot add conclusion to another professional's assignment")
    if assignment.status != models.AssignmentStatus.completed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignment must be completed before adding conclusion")
    conclusion_obj = crud.add_conclusion(db, assignment=assignment, author=current_user, content=conclusion.content)
    return schemas.ConclusionRead.from_orm(conclusion_obj)


@app.get("/professional/assignments/{assignment_id}/pdf")
def professional_download_pdf(
    assignment_id: int,
    current_user: models.User = Depends(get_current_active_professional),
    db: Session = Depends(get_db),
) -> Response:
    assignment = crud.get_assignment(db, assignment_id)
    if assignment.professional_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access this assignment")
    pdf_bytes = build_assignment_pdf(assignment, assignment.conclusion.content if assignment.conclusion else None)
    return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=assignment_{assignment_id}.pdf"})


@app.get("/client/assignments", response_model=List[schemas.AssignmentRead])
def client_assignments(
    current_user: models.User = Depends(get_current_active_client),
    db: Session = Depends(get_db),
) -> List[schemas.AssignmentRead]:
    return (
        db.query(models.Assignment)
        .filter(models.Assignment.client_id == current_user.id)
        .all()
    )


@app.post("/client/assignments/{assignment_id}/submit", response_model=schemas.AssignmentResultRead)
def client_submit_assignment(
    assignment_id: int,
    submission: schemas.AssignmentSubmission,
    current_user: models.User = Depends(get_current_active_client),
    db: Session = Depends(get_db),
) -> schemas.AssignmentResultRead:
    assignment = crud.get_assignment(db, assignment_id)
    if assignment.client_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot submit another client's assignment")
    if assignment.status == models.AssignmentStatus.completed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignment already completed")
    result = crud.submit_assignment(db, assignment=assignment, answers=[answer.dict() for answer in submission.answers])
    return result


@app.get("/client/assignments/{assignment_id}/pdf")
def client_download_pdf(
    assignment_id: int,
    current_user: models.User = Depends(get_current_active_client),
    db: Session = Depends(get_db),
) -> Response:
    assignment = crud.get_assignment(db, assignment_id)
    if assignment.client_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access this assignment")
    pdf_bytes = build_assignment_pdf(assignment, assignment.conclusion.content if assignment.conclusion else None)
    return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=my_assignment_{assignment_id}.pdf"})


@app.get("/assignments/token/{access_token}", response_model=schemas.AssignmentRead)
def get_assignment_by_public_token(access_token: str, db: Session = Depends(get_db)) -> schemas.AssignmentRead:
    assignment = crud.get_assignment_by_token(db, access_token)
    return assignment
