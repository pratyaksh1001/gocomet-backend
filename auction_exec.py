from fastapi import APIRouter,Request
from starlette.websockets import WebSocket

from database import session as sql
from cache import cache
from sqlalchemy import select

from models import Auction,Bids,User

auction_exec_router=APIRouter()
connections={}
highest={}

@auction_exec_router.get("/{auction_id}")
async def get_auction(auction_id: int):
    print(auction_id)
    q=select(Auction).where(Auction.rfq_id == auction_id)
    i=sql.execute(q).scalars().all()[0]
    d={
        "rfq_id": i.rfq_id,
        "rfq_name": i.rfq_name,
        "owner_username": i.owner.username,
        "start_time": i.start_time.isoformat(),
        "forced_close_time": i.forced_close_time.isoformat(),
        "pickup_date": i.pickup_date.isoformat(),
        "extension_duration": i.extension_duration,
        "status": i.status,
    }
    print(d)
    return {"rfq": d}
''' q=select(Bids).where(Bids.auction_id == auction_id).order_by(Bids.bid_time)
    j=sql.execute(q).scalars().all()
    t={
        "bid_amount": i.bid_amount,
        "bid_time": i.bid_time,
        "transit_time": i.transit_time,
        "freight_charges": i.freight_charges,
        "origin_charges": i.origin_charges,
        "destination_charges":i.destination_charges,
        "validity_period":i.validity_period,
        "bidder":i.owner.username,
    }'''
@auction_exec_router.websocket("/ws/{auction_id}")
async def ws_auction(auction_id: int, websocket: WebSocket):
    await websocket.accept()
    if auction_id not in connections:
        connections[auction_id] = []
    connections[auction_id].append(websocket)
    print(connections)
    try:
        while True:
            res = await websocket.receive_json()
            print(res)
            user_email=cache.hget(res["token"], "email")
            res["owner"]=select(User).where(User.email==user_email).scalars().all()[0]
            bid_amount = res["bid_amount"]
            bid=Bids(**res)
            sql.add(bid)
            if auction_id not in highest:
                highest[auction_id] = res
            else:
                if bid_amount < highest[auction_id]["bid_amount"]:
                    highest[auction_id] = res
            for ws in connections[auction_id]:
                await ws.send_json({
                    "type": "UPDATE",
                    "highest": highest[auction_id],
                    "new_bid": res
                })
            sql.commit()
    except Exception as e:
        print(e)
        connections[auction_id].remove(websocket)
