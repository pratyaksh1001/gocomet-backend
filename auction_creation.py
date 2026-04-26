from fastapi import APIRouter,Request
from database import session as sql
from sqlalchemy.sql import text
from models import Auction, User
from cache import cache
import datetime

auction_creator_router=APIRouter()

@auction_creator_router.post("")
async def auction_creator(request: Request):
    present=datetime.datetime.now()
    data=await request.json()
    print(data)
    forced_close_time=datetime.datetime.fromisoformat(data["forced_close_time"])
    start_time=datetime.datetime.fromisoformat(data["start_time"])
    token=(data["token"])
    rfq_name=(data["rfq_name"])
    extension_duration=int(data["extension_duration"])
    pickup_date=datetime.datetime.fromisoformat(data["pickup_date"])
    trigger=int(data["trigger"])
    user=cache.hgetall(token)
    if user is None:
        return {"success": False}
    print(user["email"])
    user_from_db=sql.query(User).filter(User.email==user["email"]).first()
    auction = Auction(
        rfq_name=rfq_name,
        start_time=start_time,
        forced_close_time=forced_close_time,
        pickup_date=pickup_date,
        extension_duration=extension_duration,
        owner=user_from_db,
        trigger=trigger,
        status=0 if present<start_time else 1
    )
    print(auction)
    sql.add(auction)
    sql.commit()
    return {"success": True}
