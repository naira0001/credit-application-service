from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from fastapi.security import OAuth2PasswordRequestForm
from decimal import Decimal
import models
import schemas
from database import engine, get_db
from auth import create_access_token, get_current_user, authenticate_user, get_password_hash
from datetime import timedelta

app = FastAPI(
    title="Credit Application Service",
    description="Мини-сервис для подачи заявок на кредит",
    version="1.0.0"
)

# Создание таблиц
models.Base.metadata.create_all(bind=engine)


# Автоматическое создание администратора
@app.on_event("startup")
def create_admin_user():
    db = next(get_db())
    try:
        admin = db.query(models.User).filter(models.User.username == "admin").first()
        if not admin:
            hashed_password = get_password_hash("admin123")
            admin_user = models.User(
                username="admin",
                hashed_password=hashed_password
            )
            db.add(admin_user)
            db.commit()
            print("✅ Администратор создан: admin / admin123")
        else:
            print("✅ Администратор уже существует")
    except Exception as e:
        print(f"❌ Ошибка при создании администратора: {e}")
    finally:
        db.close()


# РЕГИСТРАЦИЯ
@app.post("/register", response_model=schemas.User, summary="Регистрация пользователя")
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Регистрация нового пользователя.
    """
    try:
        if user.username == "admin":
            raise HTTPException(
                status_code=400,
                detail="Нельзя регистрироваться с именем 'admin'"
            )

        existing_user = db.query(models.User).filter(models.User.username == user.username).first()
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Пользователь с таким именем уже существует"
            )

        hashed_password = get_password_hash(user.password)
        db_user = models.User(
            username=user.username,
            hashed_password=hashed_password
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при регистрации: {str(e)}"
        )


# АВТОРИЗАЦИЯ
@app.post("/token", response_model=schemas.Token, summary="Получение токена авторизации")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Получение JWT токена для авторизации.
    """
    try:
        user = authenticate_user(db, form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверное имя пользователя или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token_expires = timedelta(minutes=30)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при авторизации: {str(e)}"
        )


# POST /applications — подача заявки
@app.post("/applications", response_model=schemas.Application, summary="Создание заявки на кредит")
def create_application(
    application: schemas.ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Создание новой заявки на кредит.

    **Автоматическая проверка:**
    - Если сумма > 100000 → статус автоматически 'rejected'
    - Если сумма ≤ 100000 → статус 'new'
    """
    try:
        # Автоматическая проверка суммы
        status_result = "rejected" if application.amount > Decimal("100000") else "new"

        db_application = models.Application(
            full_name=application.full_name,
            amount=application.amount,  # оставляем Decimal
            phone=application.phone,
            status=status_result,
            user_id=current_user.id
        )
        db.add(db_application)
        db.commit()
        db.refresh(db_application)
        return db_application

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при создании заявки: {str(e)}"
        )


# GET /applications — список заявок
@app.get("/applications", response_model=List[schemas.Application], summary="Получение списка заявок")
def get_applications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Получение списка заявок.

    **Права доступа:**
    - Обычные пользователи: видят только свои заявки
    - Администратор: видит все заявки
    """
    try:
        if current_user.username == "admin":
            applications = db.query(models.Application).all()
        else:
            applications = db.query(models.Application).filter(
                models.Application.user_id == current_user.id
            ).all()
        return applications

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении заявок: {str(e)}"
        )


# GET /applications/{id} — заявка по id
@app.get("/applications/{application_id}", response_model=schemas.Application, summary="Получение заявки по ID")
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Получение конкретной заявки по её ID.
    """
    try:
        application = db.query(models.Application).filter(models.Application.id == application_id).first()
        if application is None:
            raise HTTPException(
                status_code=404,
                detail="Заявка не найдена"
            )

        if current_user.username != "admin" and application.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Нет прав для просмотра этой заявки"
            )

        return application

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении заявки: {str(e)}"
        )


# PUT /applications/{id}/status — смена статуса
@app.put("/applications/{application_id}/status", response_model=schemas.Application, summary="Изменение статуса заявки")
def update_application_status(
    application_id: int,
    status_update: schemas.ApplicationUpdateStatus,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Изменение статуса заявки.

    **Важно:**
    - Только администратор может менять статусы
    """
    try:
        if current_user.username != "admin":
            raise HTTPException(
                status_code=403,
                detail="Только администратор может изменять статусы заявок"
            )

        application = db.query(models.Application).filter(models.Application.id == application_id).first()
        if application is None:
            raise HTTPException(
                status_code=404,
                detail="Заявка не найдена"
            )

        application.status = status_update.status
        db.commit()
        db.refresh(application)
        return application

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при изменении статуса: {str(e)}"
        )
