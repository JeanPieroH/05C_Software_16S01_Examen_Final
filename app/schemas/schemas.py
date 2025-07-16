from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class UserBase(BaseModel):
    alias: str
    name: str
    carPlate: Optional[str] = None

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int

    class Config:
        orm_mode = True

class RideParticipationBase(BaseModel):
    destination: str
    occupiedSpaces: int

class RideParticipationCreate(RideParticipationBase):
    pass

class RideParticipation(RideParticipationBase):
    id: int
    confirmation: Optional[datetime] = None
    status: str
    participant: User

    class Config:
        orm_mode = True

class RideBase(BaseModel):
    finalAddress: str
    allowedSpaces: int
    rideDateAndTime: datetime

class RideCreate(RideBase):
    pass

class Ride(RideBase):
    id: int
    status: str
    rideDriver: User
    participants: List[RideParticipation] = []

    class Config:
        orm_mode = True
