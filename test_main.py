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

@pytest.fixture(scope="function", autouse=True)
def setup_and_teardown_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_create_user_success():
    # Caso de prueba: Crear un usuario exitosamente.
    response = client.post("/usuarios/", json={"alias": "testuser", "name": "Test User", "carPlate": "TEST-123"})
    assert response.status_code == 200
    assert response.json()["alias"] == "testuser"

def test_create_user_duplicate_alias():
    # Caso de prueba: Intentar crear un usuario con un alias que ya existe.
    client.post("/usuarios/", json={"alias": "testuser", "name": "Test User", "carPlate": "TEST-123"})
    response = client.post("/usuarios/", json={"alias": "testuser", "name": "Another User", "carPlate": "ANO-456"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Alias already registered"

def test_create_ride_for_non_driver():
    # Caso de prueba: Intentar crear un ride para un usuario que no es conductor.
    client.post("/usuarios/", json={"alias": "nondriver", "name": "Non Driver User"})
    response = client.post(
        "/usuarios/nondriver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "User is not a driver"

def test_request_to_join_nonexistent_ride():
    # Caso de prueba: Intentar unirse a un ride que no existe.
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    response = client.post(
        "/usuarios/driver/rides/999/requestToJoin/participant",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Ride not found"
