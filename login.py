from fastapi import APIRouter,Request
import bcrypt
import jwt
from cache import cache
from database import session as sql
from models import User

login_router=APIRouter()
salt = bcrypt.gensalt(11)

@login_router.post("")
async def login(request: Request):
    data = await request.json()
    email = data["email"]
    password = data["password"]
    user = sql.query(User).filter(User.email == email).first()
    if user and bcrypt.checkpw(password.encode("utf-8"), user.password.encode("utf-8")):
        token = jwt.encode({"email": email, "password": password}, "pratyaksh")
        cache.hset(token, values={"email": email, "username": user.username,"role":user.role})
        cache.expire(token, 3600)
        return {"token": token, "email": email, "username": user.username, "success": True,"role":user.role}
    else:
        return {"error": "Wrong Credentials", "success": False}
