import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.routers.users import get_db
from app.models.models import Base
import os

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown_db():
    Base.metadata.create_all(bind=engine)
    yield
    os.remove("./test.db")

def test_create_user():
    response = client.post("/usuarios/", json={"alias": "testuser", "name": "Test User", "carPlate": "TEST-123"})
    assert response.status_code == 200
    assert response.json()["alias"] == "testuser"

def test_read_users():
    response = client.get("/usuarios/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_create_ride():
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    response = client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    assert response.status_code == 200
    assert response.json()["finalAddress"] == "Test Address"

def test_request_to_join_ride():
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    response = client.post(
        "/usuarios/driver/rides/1/requestToJoin/participant",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    assert response.status_code == 200
    assert response.json()["destination"] == "Participant Destination"

def test_accept_ride_request():
    response = client.post("/usuarios/driver/rides/1/accept/participant")
    assert response.status_code == 200
    assert response.json()["message"] == "Ride request accepted"

def test_start_ride():
    response = client.post("/usuarios/driver/rides/1/start")
    assert response.status_code == 200
    assert response.json()["message"] == "Ride started"

def test_unload_participant():
    response = client.post("/usuarios/participant/rides/1/unloadParticipant")
    assert response.status_code == 200
    assert response.json()["message"] == "Participant unloaded"

def test_end_ride():
    response = client.post("/usuarios/driver/rides/1/end")
    assert response.status_code == 200
    assert response.json()["message"] == "Ride ended"
