from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
import os

from database import session as sql
from sqlalchemy.sql import text


from register import register_router
from login import login_router
from auth import auth_router
from auction_creation import auction_creator_router
from home import home_router
from auction_exec import auction_exec_router

app = FastAPI()
frontend_urls = os.getenv("FRONTEND_URL", "")
env_origins = [u.strip() for u in frontend_urls.split(",") if u.strip()]
default_origins = [
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1:3001",
    "http://localhost:3001",
]
allow_origins = list(dict.fromkeys(env_origins + default_origins))
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(register_router, prefix="/register", tags=["register"])
app.include_router(login_router, prefix="/login", tags=["login"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(auction_creator_router, prefix="/auction", tags=["auction"])
app.include_router(home_router, prefix="/home", tags=["home"])
app.include_router(auction_exec_router, prefix="/auction", tags=["auction"])