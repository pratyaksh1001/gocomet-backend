import json

import jwt
from django.utils.crypto import salted_hmac
from fastapi import APIRouter,Request
import re

from models import User
from cache import cache
import bcrypt
from database import engine,SessionLocal

register_router = APIRouter()
salt = bcrypt.gensalt(11)

@register_router.post("")
async def register_user(req: Request):
    sql=SessionLocal()
    data = await req.json()
    print(data)
    password = data['password']
    res = re.fullmatch(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).+$", password)
    if res:
        data["password"] = bcrypt.hashpw(password.encode("utf-8"),salt).decode("utf-8")
        user = User(**data)
        if sql.query(User).filter(User.email == user.email).first():
            return {"message": "Email already exists", "success": False}
        sql.add(user)
        sql.commit()
        sql.close()
        return {"message": "User created successfully", "success": True}
    return {"message": "Password is weak", "success": False}