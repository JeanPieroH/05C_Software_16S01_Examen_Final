from sqlalchemy.orm import Session
from .models import models
from .schemas.schemas import UserCreate, RideCreate, RideParticipationCreate

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_alias(db: Session, alias: str):
    return db.query(models.User).filter(models.User.alias == alias).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

def create_user(db: Session, user: UserCreate):
    db_user = models.User(alias=user.alias, name=user.name, carPlate=user.carPlate)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_ride(db: Session, ride_id: int):
    return db.query(models.Ride).filter(models.Ride.id == ride_id).first()

def get_rides(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Ride).filter(models.Ride.status == "ready").offset(skip).limit(limit).all()

def create_ride(db: Session, ride: RideCreate, driver_id: int):
    db_ride = models.Ride(**ride.dict(), driver_id=driver_id)
    db.add(db_ride)
    db.commit()
    db.refresh(db_ride)
    return db_ride

def create_ride_participation(db: Session, ride_id: int, user_id: int, details: RideParticipationCreate):
    db_participation = models.RideParticipation(
        ride_id=ride_id,
        participant_id=user_id,
        destination=details.destination,
        occupiedSpaces=details.occupiedSpaces
    )
    db.add(db_participation)
    db.commit()
    db.refresh(db_participation)
    return db_participation
