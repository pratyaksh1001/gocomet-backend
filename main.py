from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
import os

from register import register_router
from login import login_router
from auth import auth_router
from auction_creation import auction_creator_router
from home import home_router
from auction_exec import auction_exec_router

app = FastAPI()
allow_origins = [
    "https://gocomet-frontend.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
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