from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import crud
from ..models import models
from ..schemas import schemas
from ..database.database import SessionLocal

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/usuarios/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_alias(db, alias=user.alias)
    if db_user:
        raise HTTPException(status_code=400, detail="Alias already registered")
    return crud.create_user(db=db, user=user)

@router.get("/usuarios/", response_model=List[schemas.User])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = crud.get_users(db, skip=skip, limit=limit)
    return users

@router.get("/usuarios/{alias}", response_model=schemas.User)
def read_user(alias: str, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_alias(db, alias=alias)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user
