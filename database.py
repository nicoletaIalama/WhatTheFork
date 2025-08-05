from sqlmodel import SQLModel, Session, create_engine, select
from models import Food

# Database setup
DATABASE_URL = "sqlite:///wtf.sqlite"
engine = create_engine(DATABASE_URL, echo=True)

def create_db_and_tables():
    """Create database and tables"""
    print("Creating database")
    SQLModel.metadata.create_all(engine)

def save_food(name: str, calories: int):
    """Save food data to the database"""
    with Session(engine) as session:
        food = Food(name=name, calories=calories)
        session.add(food)
        session.commit()
        return food

def get_all_foods():
    """Retrieve all foods from the database"""
    with Session(engine) as session:
        statement = select(Food).order_by(Food.created_at.desc())
        foods = session.exec(statement).all()
        return foods 