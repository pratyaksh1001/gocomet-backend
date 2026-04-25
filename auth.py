from fastapi import APIRouter,Request
from cache import cache
import jwt
auth_router = APIRouter()

@auth_router.post("/")
async def auth(request: Request):
    data=await request.json()
    token=data["token"]
    try:
        cached=cache.hgetall(token)
        if cached is not None:
            return {"username":cached["username"],"email":cached["email"],"success": True}
        else:
            return {"username":"","email":"","success": False}
    except:
        return {"username":"","email":"","success": False}