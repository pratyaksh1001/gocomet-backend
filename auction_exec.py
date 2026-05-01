from datetime import datetime, timedelta
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from database import SessionLocal
from models import Auction, Bids
from cache import cache

router = APIRouter()

# simple in-memory storage
connections = {}
time_left = {}
highest_bid = {}
timers = {}


# check if auction should extend
def should_extend(trigger, new_bid, current_best):
    if trigger == 1:
        return current_best is None or new_bid < current_best
    elif trigger in [2, 3]:
        return True
    return False


# background timer
async def run_timer(auction_id):
    while auction_id in time_left:
        await asyncio.sleep(1)

        time_left[auction_id] -= 1

        # stop if time over
        if time_left[auction_id] <= 0:
            await broadcast(auction_id, {
                "type": "END",
                "message": "Auction ended"
            })
            break

        # send time update
        await broadcast(auction_id, {
            "type": "TIME",
            "time_left": time_left[auction_id]
        })


# send message to all users
async def broadcast(auction_id, data):
    for ws in connections.get(auction_id, []):
        try:
            await ws.send_json(data)
        except:
            pass


@router.websocket("/ws/{auction_id}")
async def auction_ws(auction_id: int, websocket: WebSocket):
    await websocket.accept()

    # add user
    connections.setdefault(auction_id, []).append(websocket)

    try:
        # simple auth
        auth = await websocket.receive_json()
        token = auth.get("token")
        user = cache.hgetall(token) if token else None

        if not user:
            await websocket.close()
            return

        email = user.get("email")
        role = user.get("role")

        # load auction
        with SessionLocal() as db:
            auction = db.query(Auction).filter(Auction.rfq_id == auction_id).first()
            if not auction:
                await websocket.close()
                return

            now = datetime.utcnow() + timedelta(hours=5, minutes=30)
            end_time = auction.start_time + timedelta(minutes=auction.extension_duration)
            remaining = int((end_time - now).total_seconds())
            if remaining < 0:
                remaining = 0

        # start timer if not running
        if auction_id not in time_left:
            time_left[auction_id] = remaining

        if auction_id not in timers:
            timers[auction_id] = asyncio.create_task(run_timer(auction_id))

        # main loop
        while True:
            data = await websocket.receive_json()

            # only suppliers can bid
            if data.get("type") != "BID" or role != "supplier":
                continue

            amount = int(data["bid_amount"])
            now = datetime.utcnow() + timedelta(hours=5, minutes=30)

            with SessionLocal() as db:
                bid = Bids(
                    auction_id=auction_id,
                    owner_email=email,
                    bid_amount=amount,
                    bid_time=now
                )
                db.add(bid)
                db.commit()
                db.refresh(bid)

            # update best bid
            prev = highest_bid.get(auction_id)

            if auction_id not in highest_bid or amount < prev:
                highest_bid[auction_id] = amount

            # extend time if needed
            if should_extend(auction.trigger, amount, prev):
                time_left[auction_id] = auction.extension_duration * 60

                await broadcast(auction_id, {
                    "type": "EXTENDED",
                    "time_left": time_left[auction_id]
                })

            # send update
            await broadcast(auction_id, {
                "type": "NEW_BID",
                "email": email,
                "amount": amount,
                "highest": highest_bid[auction_id]
            })

    except WebSocketDisconnect:
        pass

    finally:
        # remove connection
        if websocket in connections.get(auction_id, []):
            connections[auction_id].remove(websocket)

        # cleanup if no users left
        if not connections.get(auction_id):
            connections.pop(auction_id, None)
            time_left.pop(auction_id, None)
            highest_bid.pop(auction_id, None)

            if auction_id in timers:
                timers[auction_id].cancel()
                timers.pop(auction_id, None)