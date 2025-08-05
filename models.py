from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class Food(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    calories: int
    created_at: datetime = Field(default_factory=datetime.utcnow) 
