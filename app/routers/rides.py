from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import crud
from ..models import models
from ..schemas import schemas
from ..database.database import SessionLocal
from datetime import datetime

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/usuarios/{alias}/rides", response_model=schemas.Ride)
def create_ride_for_user(alias: str, ride: schemas.RideCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_alias(db, alias=alias)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    if not db_user.carPlate:
        raise HTTPException(status_code=422, detail="User is not a driver")
    return crud.create_ride(db=db, ride=ride, driver_id=db_user.id)

@router.get("/rides", response_model=List[schemas.Ride])
def read_rides(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    rides = crud.get_rides(db, skip=skip, limit=limit)
    return rides

@router.get("/usuarios/{alias}/rides", response_model=List[schemas.Ride])
def read_user_rides(alias: str, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_alias(db, alias=alias)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user.rides

@router.get("/usuarios/{alias}/rides/{ride_id}", response_model=schemas.Ride)
def read_ride(alias: str, ride_id: int, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_alias(db, alias=alias)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db_ride = crud.get_ride(db, ride_id=ride_id)
    if not db_ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    return db_ride

@router.post("/usuarios/{alias}/rides/{ride_id}/requestToJoin/{participant_alias}", response_model=schemas.RideParticipation)
def request_to_join_ride(alias: str, ride_id: int, participant_alias: str, participation_details: schemas.RideParticipationCreate, db: Session = Depends(get_db)):
    db_driver = crud.get_user_by_alias(db, alias=alias)
    if not db_driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    db_ride = crud.get_ride(db, ride_id=ride_id)
    if not db_ride or db_ride.rideDriver.id != db_driver.id:
        raise HTTPException(status_code=404, detail="Ride not found")

    if db_ride.status != "ready":
        raise HTTPException(status_code=422, detail="Ride is not ready to accept requests")

    db_participant = crud.get_user_by_alias(db, alias=participant_alias)
    if not db_participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    if db_driver.id == db_participant.id:
        raise HTTPException(status_code=422, detail="Driver cannot join their own ride")

    existing_participation = any(p.participant_id == db_participant.id for p in db_ride.participants)
    if existing_participation:
        raise HTTPException(status_code=422, detail="Participant has already requested to join this ride")

    return crud.create_ride_participation(db=db, ride_id=ride_id, user_id=db_participant.id, details=participation_details)

@router.post("/usuarios/{alias}/rides/{ride_id}/accept/{participant_alias}")
def accept_ride_request(alias: str, ride_id: int, participant_alias: str, db: Session = Depends(get_db)):
    db_driver = crud.get_user_by_alias(db, alias=alias)
    if not db_driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    db_ride = crud.get_ride(db, ride_id=ride_id)
    if not db_ride or db_ride.rideDriver.id != db_driver.id:
        raise HTTPException(status_code=404, detail="Ride not found")

    db_participant = crud.get_user_by_alias(db, alias=participant_alias)
    if not db_participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    participation = next((p for p in db_ride.participants if p.participant_id == db_participant.id), None)
    if not participation:
        raise HTTPException(status_code=404, detail="Participation request not found")

    if participation.status != "waiting":
        raise HTTPException(status_code=422, detail="Participation request is not waiting for confirmation")

    confirmed_spaces = sum(p.occupiedSpaces for p in db_ride.participants if p.status == 'confirmed')
    if db_ride.allowedSpaces < confirmed_spaces + participation.occupiedSpaces:
        raise HTTPException(status_code=422, detail="Not enough spaces available")

    participation.status = "confirmed"
    participation.confirmation = datetime.utcnow()
    db.commit()
    return {"message": "Ride request accepted"}

@router.post("/usuarios/{alias}/rides/{ride_id}/reject/{participant_alias}")
def reject_ride_request(alias: str, ride_id: int, participant_alias: str, db: Session = Depends(get_db)):
    db_driver = crud.get_user_by_alias(db, alias=alias)
    if not db_driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    db_ride = crud.get_ride(db, ride_id=ride_id)
    if not db_ride or db_ride.rideDriver.id != db_driver.id:
        raise HTTPException(status_code=404, detail="Ride not found")

    db_participant = crud.get_user_by_alias(db, alias=participant_alias)
    if not db_participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    participation = next((p for p in db_ride.participants if p.participant_id == db_participant.id), None)
    if not participation:
        raise HTTPException(status_code=404, detail="Participation request not found")

    if participation.status != "waiting":
        raise HTTPException(status_code=422, detail="Participation request is not waiting for confirmation")

    participation.status = "rejected"
    db.commit()
    return {"message": "Ride request rejected"}

@router.post("/usuarios/{alias}/rides/{ride_id}/start")
def start_ride(alias: str, ride_id: int, db: Session = Depends(get_db)):
    db_driver = crud.get_user_by_alias(db, alias=alias)
    if not db_driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    db_ride = crud.get_ride(db, ride_id=ride_id)
    if not db_ride or db_ride.rideDriver.id != db_driver.id:
        raise HTTPException(status_code=404, detail="Ride not found")

    if any(p.status == "waiting" for p in db_ride.participants):
        raise HTTPException(status_code=422, detail="There are pending participation requests")

    db_ride.status = "inprogress"
    for p in db_ride.participants:
        if p.status == "confirmed":
            p.status = "inprogress"
        else:
            p.status = "missing"
    db.commit()
    return {"message": "Ride started"}

@router.post("/usuarios/{alias}/rides/{ride_id}/end")
def end_ride(alias: str, ride_id: int, db: Session = Depends(get_db)):
    db_driver = crud.get_user_by_alias(db, alias=alias)
    if not db_driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    db_ride = crud.get_ride(db, ride_id=ride_id)
    if not db_ride or db_ride.rideDriver.id != db_driver.id:
        raise HTTPException(status_code=404, detail="Ride not found")

    db_ride.status = "done"
    for p in db_ride.participants:
        if p.status == "inprogress":
            p.status = "notmarked"
    db.commit()
    return {"message": "Ride ended"}

@router.post("/usuarios/{alias}/rides/{ride_id}/unloadParticipant")
def unload_participant(alias: str, ride_id: int, db: Session = Depends(get_db)):
    db_participant = crud.get_user_by_alias(db, alias=alias)
    if not db_participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    db_ride = crud.get_ride(db, ride_id=ride_id)
    if not db_ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    participation = next((p for p in db_ride.participants if p.participant_id == db_participant.id), None)
    if not participation:
        raise HTTPException(status_code=404, detail="Participant not in this ride")

    if participation.status != "inprogress":
        raise HTTPException(status_code=422, detail="Participant is not in an in-progress ride")

    participation.status = "done"
    db.commit()
    return {"message": "Participant unloaded"}
