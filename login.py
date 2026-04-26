from fastapi import APIRouter,Request
import bcrypt
import jwt
from sqlalchemy.orm import Session

from cache import cache
from database import engine, SessionLocal
from models import User

login_router=APIRouter()
salt = bcrypt.gensalt(11)

@login_router.post("")
async def login(request: Request):
    sql=SessionLocal()
    data = await request.json()
    email = data["email"]
    password = data["password"]
    user = sql.query(User).filter(User.email == email).first()
    sql.close()
    if user and bcrypt.checkpw(password.encode("utf-8"), user.password.encode("utf-8")):
        token = jwt.encode({"email": email, "password": password}, "pratyaksh")
        cache.hset(token, values={"email": email, "username": user.username,"role":user.role})
        cache.expire(token, 3600)
        return {"token": token, "email": email, "username": user.username, "success": True,"role":user.role}
    else:
        return {"error": "Wrong Credentials", "success": False}
