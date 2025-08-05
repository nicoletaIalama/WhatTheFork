from sqlmodel import SQLModel, Session, create_engine, select
from models import Food, Account

# Database setup
DATABASE_URL = "sqlite:///wtf.sqlite"
engine = create_engine(DATABASE_URL, echo=True)

def create_db_and_tables():
    """Create database and tables"""
    print("Creating database")
    SQLModel.metadata.create_all(engine)

def save_food(name: str, calories: int, fats: int = 0, proteins: int = 0, carbs: int = 0):
    """Save food data to the database"""
    with Session(engine) as session:
        food = Food(name=name, calories=calories, fats=fats, proteins=proteins, carbs=carbs)
        session.add(food)
        session.commit()
        session.refresh(food)
        return food

def get_all_foods():
    """Retrieve all foods from the database"""
    with Session(engine) as session:
        statement = select(Food).order_by(Food.created_at.desc())
        foods = session.exec(statement).all()
        return foods

def get_account():
    """Fetch the first account or return None if no accounts exist"""
    with Session(engine) as session:
        statement = select(Account).limit(1)
        account = session.exec(statement).first()
        return account 