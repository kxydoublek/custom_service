from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class LoginData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class LogoutData(BaseModel):
    logged_out: bool = True
