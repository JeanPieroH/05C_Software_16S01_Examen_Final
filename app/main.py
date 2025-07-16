from fastapi import FastAPI
from .database import database
from .routers import users, rides

app = FastAPI()

database.init_db()

app.include_router(users.router)
app.include_router(rides.router)
