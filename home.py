import datetime

from sqlalchemy import select
from fastapi import APIRouter,Request
from database import session as sql
from cache import cache
from models import Auction, Bids
home_router=APIRouter()


@home_router.get("")
async def home(request: Request):
    try:
        status = request.query_params["status"]
        if status == "active":
            status =1
        elif status == "closed":
            status = 0
        elif status == "forced":
            status = 2
        else:
            status = -1
        print(status)
        present=datetime.datetime.now()
        auctions = sql.execute(select(Auction)).scalars().all()
        updated = False
        for a in auctions:
            latest_bid = (
                sql.query(Bids)
                .filter(Bids.auction_id == a.rfq_id)
                .order_by(Bids.bid_time.desc())
                .first()
            )
            base_time = latest_bid.bid_time if latest_bid else a.start_time
            dynamic_close = base_time + datetime.timedelta(minutes=a.extension_duration)
            effective_close = min(dynamic_close, a.forced_close_time)
            if present >= effective_close:
                next_status = 2 if effective_close == a.forced_close_time else 0
            else:
                next_status = 1
            if a.status != next_status:
                a.status = next_status
                updated = True
        if updated:
            sql.commit()
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