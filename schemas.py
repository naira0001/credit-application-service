from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, Annotated
from datetime import datetime
from decimal import Decimal


# Для заявок
class ApplicationBase(BaseModel):
    full_name: Annotated[str, Field(
        min_length=2,
        max_length=100,
        description="ФИО клиента",
        json_schema_extra={"example": "Иванов Иван Иванович"}
    )]
    amount: Annotated[Decimal, Field(
        gt=0,
        description="Сумма кредита (только цифры)",
        json_schema_extra={"example": 50000.0}
    )]
    phone: Annotated[str, Field(
        description="Номер телефона (10–15 цифр, можно с +)",
        json_schema_extra={"example": "+79991234567"}
    )]

    # --- Validators ---
    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("ФИО не может быть пустым")
        if len(v.strip()) < 2:
            raise ValueError("ФИО должно содержать минимум 2 символа")
        return v.strip()

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """
        Валидация суммы кредита.
        Только проверяет, что сумма положительная.
        """
        try:
            if v <= 0:
                raise ValueError("Сумма должна быть больше 0")
            return v
        except (ValueError, TypeError):
            raise ValueError("Сумма должна быть числом, не прописью! Введите цифры, например: 50000")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not v:
            raise ValueError("Телефон не может быть пустым")
        clean_phone = "".join(filter(str.isdigit, v))
        if len(clean_phone) < 10:
            raise ValueError("Телефон должен содержать минимум 10 цифр")
        if len(clean_phone) > 15:
            raise ValueError("Телефон слишком длинный")
        # Возвращаем нормализованный формат: всегда с +
        return f"+{clean_phone}"


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationUpdateStatus(BaseModel):
    status: Literal["new", "approved", "rejected"] = Field(
        description="Статус заявки",
        json_schema_extra={"example": "approved"}
    )


class Application(ApplicationBase):
    id: int
    status: str
    created_at: datetime
    user_id: int

    class Config:
        from_attributes = True


# Для авторизации
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# Для пользователей
class UserBase(BaseModel):
    username: Annotated[str, Field(
        min_length=3,
        max_length=50,
        description="Имя пользователя",
        json_schema_extra={"example": "user123"}
    )]

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not v:
            raise ValueError("Имя пользователя не может быть пустым")
        if " " in v:
            raise ValueError("Имя пользователя не должно содержать пробелы")
        return v


class UserCreate(UserBase):
    password: Annotated[str, Field(
        min_length=6,
        description="Пароль (минимум 6 символов)",
        json_schema_extra={"example": "password123"}
    )]

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v:
            raise ValueError("Пароль не может быть пустым")
        if len(v) < 6:
            raise ValueError("Пароль должен содержать минимум 6 символов")
        return v


class User(UserBase):
    id: int
    hashed_password: str

    class Config:
        from_attributes = True