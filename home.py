import datetime

from sqlalchemy import select
from fastapi import APIRouter,Request
from database import session as sql
from cache import cache
from models import Auction
home_router=APIRouter()


@home_router.get("")
async def home(request: Request):
    try:
        status = request.query_params["status"]
        if status == "active":
            status =1
        elif status == "closed":
            status = 0
        else:
            status = -1
        print(status)
        present=datetime.datetime.now()
        q=select(Auction).where(Auction.status==status)
        res = sql.execute(q).scalars().all()
        result = [
            {
                "rfq_id": i.rfq_id,
                "rfq_name": i.rfq_name,
                "owner_username": i.owner.username,
                "start_time": i.start_time.isoformat(),
                "forced_close_time": i.forced_close_time.isoformat(),
                "pickup_date": i.pickup_date.isoformat(),
                "extension_duration": i.extension_duration,
                "status":i.status,
            }
            for i in res
        ]
        print(result)

        return {"result": result,"success": True}

    except Exception as e:
        print(e)
        return {"result": [], "success": False}