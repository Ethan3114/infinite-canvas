"""请求和响应的形状。"""

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    code: str = Field(min_length=1, max_length=80)


class ProfileIn(BaseModel):
    elder_name: str = Field(min_length=1, max_length=40)
    birth_year: int | None = Field(default=None, ge=1900, le=2026)
    hometown: str = Field(default="", max_length=80)
    family_names: str = Field(default="", max_length=200)
    topics_want: str = Field(default="", max_length=500)
    topics_avoid: str = Field(default="", max_length=500)


class CallIn(BaseModel):
    profile_id: str
    consent: bool


class ScoreIn(BaseModel):
    score: int = Field(ge=1, le=3)


class FactIn(BaseModel):
    status: str = Field(pattern="^(open|confirmed|rejected)$")
    detail: str = Field(default="", max_length=500)
