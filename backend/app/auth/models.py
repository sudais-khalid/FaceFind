from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID


class UserResponse(BaseModel):
    user_id: UUID
    email: str
    name: Optional[str]
    consent_given: bool

    class Config:
        from_attributes = True


class AuthCallbackRequest(BaseModel):
    code: str
    state: str


class RefreshTokenRequest(BaseModel):
    pass


class LoginResponse(BaseModel):
    redirect_url: str
