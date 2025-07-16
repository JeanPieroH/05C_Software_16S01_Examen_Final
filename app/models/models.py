from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    alias = Column(String, unique=True, index=True)
    name = Column(String)
    carPlate = Column(String, nullable=True)
    rides = relationship("Ride", back_populates="rideDriver")

class Ride(Base):
    __tablename__ = 'rides'
    id = Column(Integer, primary_key=True, index=True)
    rideDateAndTime = Column(DateTime)
    finalAddress = Column(String)
    allowedSpaces = Column(Integer)
    driver_id = Column(Integer, ForeignKey('users.id'))
    status = Column(String, default="ready")
    rideDriver = relationship("User", back_populates="rides")
    participants = relationship("RideParticipation", back_populates="ride")

class RideParticipation(Base):
    __tablename__ = 'ride_participations'
    id = Column(Integer, primary_key=True, index=True)
    confirmation = Column(DateTime, nullable=True)
    destination = Column(String)
    occupiedSpaces = Column(Integer)
    status = Column(String, default="waiting")
    ride_id = Column(Integer, ForeignKey('rides.id'))
    participant_id = Column(Integer, ForeignKey('users.id'))
    ride = relationship("Ride", back_populates="participants")
    participant = relationship("User")
