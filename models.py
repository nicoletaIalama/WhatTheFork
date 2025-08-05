from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional


class Account(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    height_cm: int
    weight_kg: int
    age: int
    gender: str
    target_weight_kg: int
    daily_calorie_target: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Food(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    calories: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
