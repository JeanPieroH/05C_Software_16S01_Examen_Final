import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.routers.users import get_db
from app.models.models import Base
import os
from datetime import datetime

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

def test_read_user_not_found():
    # Caso de prueba: Intentar leer un usuario que no existe.
    response = client.get("/usuarios/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"

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

def test_read_rides():
    # Caso de prueba: Leer los rides activos
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    response = client.get("/rides")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) > 0

def test_read_user_rides():
    # Caso de prueba: Leer los rides de un usuario
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    response = client.get("/usuarios/driver/rides")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) > 0

def test_reject_ride_request():
    # Caso de prueba: Rechazar una solicitud de ride
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    client.post(
        "/usuarios/driver/rides/1/requestToJoin/participant",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    response = client.post("/usuarios/driver/rides/1/reject/participant")
    assert response.status_code == 200
    assert response.json()["message"] == "Ride request rejected"

def test_start_ride_with_pending_requests():
    # Caso de prueba: Intentar iniciar un ride con solicitudes pendientes
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    client.post(
        "/usuarios/driver/rides/1/requestToJoin/participant",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    response = client.post("/usuarios/driver/rides/1/start")
    assert response.status_code == 422
    assert response.json()["detail"] == "There are pending participation requests"

def test_end_ride_with_inprogress_participant():
    # Caso de prueba: Terminar un ride con un participante en progreso
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    client.post(
        "/usuarios/driver/rides/1/requestToJoin/participant",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    client.post("/usuarios/driver/rides/1/accept/participant")
    client.post("/usuarios/driver/rides/1/start")
    response = client.post("/usuarios/driver/rides/1/end")
    assert response.status_code == 200
    assert response.json()["message"] == "Ride ended"

def test_get_user():
    # Caso de prueba: Obtener un usuario por ID
    user_res = client.post("/usuarios/", json={"alias": "testuser", "name": "Test User", "carPlate": "TEST-123"})
    user_id = user_res.json()["id"]
    response = client.get(f"/usuarios/testuser")
    assert response.status_code == 200
    assert response.json()["id"] == user_id

def test_get_ride():
    # Caso de prueba: Obtener un ride por ID
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    ride_res = client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    ride_id = ride_res.json()["id"]
    response = client.get(f"/usuarios/driver/rides/{ride_id}")
    assert response.status_code == 200
    assert response.json()["id"] == ride_id

def test_unload_participant_not_in_ride():
    # Caso de prueba: Intentar descargar a un participante que no está en el ride
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    response = client.post("/usuarios/participant/rides/1/unloadParticipant")
    assert response.status_code == 404
    assert response.json()["detail"] == "Participant not in this ride"

def test_accept_ride_request_no_space():
    # Caso de prueba: Aceptar una solicitud de viaje cuando no hay espacio
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "p1", "name": "Participant 1"})
    client.post("/usuarios/", json={"alias": "p2", "name": "Participant 2"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 1}
    )
    client.post(
        "/usuarios/driver/rides/1/requestToJoin/p1",
        json={"destination": "P1 Destination", "occupiedSpaces": 1}
    )
    client.post(
        "/usuarios/driver/rides/1/requestToJoin/p2",
        json={"destination": "P2 Destination", "occupiedSpaces": 1}
    )
    client.post("/usuarios/driver/rides/1/accept/p1")
    response = client.post("/usuarios/driver/rides/1/accept/p2")
    assert response.status_code == 422
    assert response.json()["detail"] == "Not enough spaces available"

def test_request_to_join_ride_not_ready():
    # Caso de prueba: Solicitar unirse a un viaje que no está listo
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    client.post(
        "/usuarios/driver/rides/1/requestToJoin/participant",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    client.post("/usuarios/driver/rides/1/accept/participant")
    client.post("/usuarios/driver/rides/1/start")
    response = client.post(
        "/usuarios/driver/rides/1/requestToJoin/participant",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Ride is not ready to accept requests"

def test_get_user_by_id():
    # Caso de prueba: Obtener un usuario por ID
    user_res = client.post("/usuarios/", json={"alias": "testuser", "name": "Test User", "carPlate": "TEST-123"})
    user_id = user_res.json()["id"]
    from app.crud import get_user
    db = TestingSessionLocal()
    user = get_user(db, user_id)
    db.close()
    assert user is not None
    assert user.id == user_id

def test_get_users():
    # Caso de prueba: Obtener todos los usuarios
    client.post("/usuarios/", json={"alias": "testuser1", "name": "Test User 1"})
    client.post("/usuarios/", json={"alias": "testuser2", "name": "Test User 2"})
    response = client.get("/usuarios/")
    assert response.status_code == 200
    assert len(response.json()) == 2

def test_create_ride():
    # Caso de prueba: Crear un ride
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    response = client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    assert response.status_code == 200
    assert response.json()["finalAddress"] == "Test Address"

def test_request_to_join_ride():
    # Caso de prueba: Solicitar unirse a un ride
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    response = client.post(
        "/usuarios/driver/rides/1/requestToJoin/participant",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    assert response.status_code == 200
    assert response.json()["destination"] == "Participant Destination"

def test_accept_ride_request():
    # Caso de prueba: Aceptar una solicitud de ride
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    client.post(
        "/usuarios/driver/rides/1/requestToJoin/participant",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    response = client.post("/usuarios/driver/rides/1/accept/participant")
    assert response.status_code == 200
    assert response.json()["message"] == "Ride request accepted"

def test_start_ride():
    # Caso de prueba: Iniciar un ride
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    client.post(
        "/usuarios/driver/rides/1/requestToJoin/participant",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    client.post("/usuarios/driver/rides/1/accept/participant")
    response = client.post("/usuarios/driver/rides/1/start")
    assert response.status_code == 200
    assert response.json()["message"] == "Ride started"

def test_unload_participant():
    # Caso de prueba: Descargar a un participante
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    client.post(
        "/usuarios/driver/rides/1/requestToJoin/participant",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    client.post("/usuarios/driver/rides/1/accept/participant")
    client.post("/usuarios/driver/rides/1/start")
    response = client.post("/usuarios/participant/rides/1/unloadParticipant")
    assert response.status_code == 200
    assert response.json()["message"] == "Participant unloaded"

def test_create_ride_for_nonexistent_user():
    # Caso de prueba: Crear un ride para un usuario que no existe
    response = client.post(
        "/usuarios/nonexistent/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"

def test_read_user_rides_for_nonexistent_user():
    # Caso de prueba: Leer los rides de un usuario que no existe
    response = client.get("/usuarios/nonexistent/rides")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"

def test_read_ride_for_nonexistent_user():
    # Caso de prueba: Leer un ride de un usuario que no existe
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    ride_res = client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    ride_id = ride_res.json()["id"]
    response = client.get(f"/usuarios/nonexistent/rides/{ride_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"

def test_read_ride_not_found():
    # Caso de prueba: Leer un ride que no existe
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    response = client.get("/usuarios/driver/rides/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Ride not found"

def test_request_to_join_ride_as_driver():
    # Caso de prueba: El conductor de un ride intenta unirse a su propio ride
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    response = client.post(
        "/usuarios/driver/rides/1/requestToJoin/driver",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Driver cannot join their own ride"

def test_reject_ride_request_not_waiting():
    # Caso de prueba: Rechazar una solicitud de ride que no está en estado "waiting"
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    client.post(
        "/usuarios/driver/rides/1/requestToJoin/participant",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    client.post("/usuarios/driver/rides/1/accept/participant")
    response = client.post("/usuarios/driver/rides/1/reject/participant")
    assert response.status_code == 422
    assert response.json()["detail"] == "Participation request is not waiting for confirmation"

def test_unload_participant_not_in_progress():
    # Caso de prueba: Descargar a un participante que no está en un ride en progreso
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    client.post(
        "/usuarios/driver/rides/1/requestToJoin/participant",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    client.post("/usuarios/driver/rides/1/accept/participant")
    response = client.post("/usuarios/participant/rides/1/unloadParticipant")
    assert response.status_code == 422
    assert response.json()["detail"] == "Participant is not in an in-progress ride"

def test_reject_nonexistent_request():
    # Caso de prueba: Rechazar una solicitud de ride que no existe
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    response = client.post("/usuarios/driver/rides/1/reject/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Participant not found"

def test_accept_nonexistent_request():
    # Caso de prueba: Aceptar una solicitud de ride que no existe
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    response = client.post("/usuarios/driver/rides/1/accept/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Participant not found"

def test_start_nonexistent_ride():
    # Caso de prueba: Iniciar un ride que no existe
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    response = client.post("/usuarios/driver/rides/999/start")
    assert response.status_code == 404
    assert response.json()["detail"] == "Ride not found"

def test_end_nonexistent_ride():
    # Caso de prueba: Terminar un ride que no existe
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    response = client.post("/usuarios/driver/rides/999/end")
    assert response.status_code == 404
    assert response.json()["detail"] == "Ride not found"

def test_unload_nonexistent_participant():
    # Caso de prueba: Descargar a un participante que no existe
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    response = client.post("/usuarios/nonexistent/rides/1/unloadParticipant")
    assert response.status_code == 404
    assert response.json()["detail"] == "Participant not found"

def test_unload_participant_from_nonexistent_ride():
    # Caso de prueba: Descargar a un participante de un ride que no existe
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    response = client.post("/usuarios/participant/rides/999/unloadParticipant")
    assert response.status_code == 404
    assert response.json()["detail"] == "Ride not found"

def test_request_to_join_ride_twice():
    # Caso de prueba: Intentar unirse a un ride dos veces
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    client.post(
        "/usuarios/driver/rides/1/requestToJoin/participant",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    response = client.post(
        "/usuarios/driver/rides/1/requestToJoin/participant",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Participant has already requested to join this ride"

def test_accept_request_for_nonexistent_ride():
    # Caso de prueba: Aceptar una solicitud para un ride que no existe
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    response = client.post("/usuarios/driver/rides/999/accept/participant")
    assert response.status_code == 404
    assert response.json()["detail"] == "Ride not found"

def test_reject_request_for_nonexistent_ride():
    # Caso de prueba: Rechazar una solicitud para un ride que no existe
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    response = client.post("/usuarios/driver/rides/999/reject/participant")
    assert response.status_code == 404
    assert response.json()["detail"] == "Ride not found"

def test_start_ride_by_non_driver():
    # Caso de prueba: Iniciar un ride por un usuario que no es el conductor
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "another_user", "name": "Another User"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    response = client.post("/usuarios/another_user/rides/1/start")
    assert response.status_code == 404
    assert response.json()["detail"] == "Ride not found"

def test_end_ride_by_non_driver():
    # Caso de prueba: Terminar un ride por un usuario que no es el conductor
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "another_user", "name": "Another User"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    response = client.post("/usuarios/another_user/rides/1/end")
    assert response.status_code == 404
    assert response.json()["detail"] == "Ride not found"

def test_request_to_join_nonexistent_participant():
    # Caso de prueba: Solicitar unirse a un ride con un participante que no existe
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    response = client.post(
        "/usuarios/driver/rides/1/requestToJoin/nonexistent",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Participant not found"

def test_reject_request_by_non_driver():
    # Caso de prueba: Rechazar una solicitud de ride por un usuario que no es el conductor
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    client.post("/usuarios/", json={"alias": "another_user", "name": "Another User"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    client.post(
        "/usuarios/driver/rides/1/requestToJoin/participant",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    response = client.post("/usuarios/another_user/rides/1/reject/participant")
    assert response.status_code == 404
    assert response.json()["detail"] == "Ride not found"

def test_accept_request_by_non_driver():
    # Caso de prueba: Aceptar una solicitud de ride por un usuario que no es el conductor
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "participant", "name": "Participant User"})
    client.post("/usuarios/", json={"alias": "another_user", "name": "Another User"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    client.post(
        "/usuarios/driver/rides/1/requestToJoin/participant",
        json={"destination": "Participant Destination", "occupiedSpaces": 1}
    )
    response = client.post("/usuarios/another_user/rides/1/accept/participant")
    assert response.status_code == 404
    assert response.json()["detail"] == "Ride not found"

def test_accept_request_for_nonexistent_participant():
    # Caso de prueba: Aceptar una solicitud de ride para un participante que no existe
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    response = client.post("/usuarios/driver/rides/1/accept/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Participant not found"

def test_reject_request_for_nonexistent_participant():
    # Caso de prueba: Rechazar una solicitud de ride para un participante que no existe
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    response = client.post("/usuarios/driver/rides/1/reject/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Participant not found"

def test_start_ride_with_missing_participant():
    # Caso de prueba: Iniciar un ride con un participante que falta
    client.post("/usuarios/", json={"alias": "driver", "name": "Driver User", "carPlate": "DRIVE-123"})
    client.post("/usuarios/", json={"alias": "p1", "name": "Participant 1"})
    client.post(
        "/usuarios/driver/rides",
        json={"rideDateAndTime": "2025-07-15T22:00:00", "finalAddress": "Test Address", "allowedSpaces": 3}
    )
    client.post(
        "/usuarios/driver/rides/1/requestToJoin/p1",
        json={"destination": "P1 Destination", "occupiedSpaces": 1}
    )
    client.post("/usuarios/driver/rides/1/reject/p1")
    response = client.post("/usuarios/driver/rides/1/start")
    assert response.status_code == 200
    assert response.json()["message"] == "Ride started"

def test_read_users_with_skip_and_limit():
    # Caso de prueba: Leer usuarios con skip y limit
    client.post("/usuarios/", json={"alias": "testuser1", "name": "Test User 1"})
    client.post("/usuarios/", json={"alias": "testuser2", "name": "Test User 2"})
    client.post("/usuarios/", json={"alias": "testuser3", "name": "Test User 3"})
    response = client.get("/usuarios/?skip=1&limit=1")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["alias"] == "testuser2"
