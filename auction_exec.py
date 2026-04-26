from datetime import datetime, timedelta
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from database import session as sql
from cache import cache
from models import Auction, Bids

auction_exec_router = APIRouter()

connections = {}
highest = {}
time_remaining = {}
timer_tasks = {}
current_end_time = {}


def refresh_auction_status(auction):
    now = datetime.now()
    if auction.forced_close_time <= now:
        auction.status = 2
        return auction.status, 0
    latest_bid = (
        sql.query(Bids)
        .filter(Bids.auction_id == auction.rfq_id)
        .order_by(Bids.bid_time.desc())
        .first()
    )
    base_time = latest_bid.bid_time if latest_bid else auction.start_time
    dynamic_close = base_time + timedelta(minutes=auction.extension_duration)
    effective_close = min(dynamic_close, auction.forced_close_time)
    remaining = int((effective_close - now).total_seconds())
    if remaining <= 0:
        auction.status = 0
        return auction.status, 0
    auction.status = 1
    return auction.status, remaining


@auction_exec_router.get("/{auction_id}")
async def get_auction(auction_id: int):
    auction = sql.query(Auction).filter(Auction.rfq_id == auction_id).first()
    if not auction:
        return {"success": False, "rfq": None}

    status, remaining = refresh_auction_status(auction)
    sql.commit()
    bids = sql.query(Bids).filter(Bids.auction_id == auction_id).all()
    now = datetime.now()
    return {
        "success": True,
        "rfq": {
            "rfq_id": auction.rfq_id,
            "rfq_name": auction.rfq_name,
            "owner_email": auction.owner_email,
            "start_time": auction.start_time.isoformat(),
            "forced_close_time": auction.forced_close_time.isoformat(),
            "pickup_date": auction.pickup_date.isoformat(),
            "extension_duration": auction.extension_duration,
            "status": status,
            "trigger": auction.trigger,
            "current_end_time": (now + timedelta(seconds=remaining)).isoformat() if remaining > 0 else now.isoformat(),
            "time_remaining": remaining,
            "bids": [
                {
                    "bid_id": b.bid_id,
                    "auction_id": b.auction_id,
                    "owner_email": b.owner_email,
                    "bid_amount": b.bid_amount,
                    "bid_time": b.bid_time.isoformat(),
                    "transit_time": b.transit_time,
                    "freight_charges": b.freight_charges,
                    "origin_charges": b.origin_charges,
                    "destination_charges": b.destination_charges,
                    "validity_period": b.validity_period.isoformat() if b.validity_period else None
                }
                for b in bids
            ]
        }
    }


def should_extend(auction, new_bid, previous_best):
    if auction.trigger == 1:
        return (
            previous_best is None or
            new_bid["bid_amount"] < previous_best["bid_amount"]
        )
    elif auction.trigger == 2:
        return True
    elif auction.trigger == 3:
        return True
    return False


async def timer_loop(auction_id: int):
    while True:
        if auction_id not in time_remaining:
            break

        auction = sql.query(Auction).filter(
            Auction.rfq_id == auction_id
        ).first()

        now = datetime.now()

        max_allowed = int(
            (auction.forced_close_time - now).total_seconds()
        )

        if max_allowed <= 0:
            auction.status = 2
            sql.commit()
            time_remaining[auction_id] = 0
            current_end_time[auction_id] = now
            for ws in connections.get(auction_id, []):
                await ws.send_json({
                    "type": "TIME_UPDATE",
                    "time_remaining": 0,
                    "current_end_time": now.isoformat(),
                    "status": "forced"
                })
            break

        if time_remaining[auction_id] > max_allowed:
            time_remaining[auction_id] = max_allowed

        current_end_time[auction_id] = now

        if time_remaining[auction_id] <= 0:
            auction.status = 0
            sql.commit()

            for ws in connections.get(auction_id, []):
                await ws.send_json({
                    "type": "TIME_UPDATE",
                    "time_remaining": 0,
                    "current_end_time": now.isoformat(),
                    "status": "closed"
                })

            break

        time_remaining[auction_id] -= 1

        dead = []
        for ws in connections.get(auction_id, []):
            try:
                await ws.send_json({
                    "type": "TIME_UPDATE",
                    "time_remaining": time_remaining[auction_id],
                    "current_end_time": (
                        now + timedelta(seconds=time_remaining[auction_id])
                    ).replace(microsecond=0).isoformat(),
                    "status": "active",
                    "monitoring": max_allowed <= 600
                })
            except:
                dead.append(ws)

        for d in dead:
            connections[auction_id].remove(d)

        await asyncio.sleep(1)


@auction_exec_router.websocket("/ws/{auction_id}")
async def ws_auction(auction_id: int, websocket: WebSocket):
    await websocket.accept()
    connections.setdefault(auction_id, []).append(websocket)
    try:
        auth = await websocket.receive_json()

        if auth.get("type") != "AUTH":
            await websocket.close()
            return
        token = auth.get("token")
        user_email = cache.hget(token, "email")
        role = cache.hget(token, "role")

        if not user_email or role not in ("supplier", "buyer"):
            await websocket.close()
            return
        auction = sql.query(Auction).filter(
            Auction.rfq_id == auction_id
        ).first()
        if not auction:
            await websocket.close()
            return
        if auction_id not in time_remaining:
            now = datetime.now()
            status, remaining = refresh_auction_status(auction)
            sql.commit()
            if status in (0, 2):
                await websocket.send_json({
                    "type": "TIME_UPDATE",
                    "time_remaining": 0,
                    "current_end_time": now.isoformat(),
                    "status": "closed" if status == 0 else "forced"
                })
                await websocket.close()
                return
            time_remaining[auction_id] = remaining
            current_end_time[auction_id] = now + timedelta(seconds=remaining)

        if auction_id not in timer_tasks:
            timer_tasks[auction_id] = asyncio.create_task(
                timer_loop(auction_id)
            )
        while True:
            res = await websocket.receive_json()
            if res.get("type") != "BID":
                continue
            if role != "supplier":
                continue
            if auction.status in (0, 2):
                continue
            try:
                bid_amount = int(res["bid_amount"])
                freight = int(res["freight_charges"])
                origin = int(res["origin_charges"])
                dest = int(res["destination_charges"])
                transit = int(res["transit_time"])
                validity = (
                    datetime.fromisoformat(res["validity_period"])
                    if res.get("validity_period")
                    else None
                )
            except Exception:
                continue
            now = datetime.now()
            if now >= auction.forced_close_time:
                auction.status = 2
                sql.commit()
                for ws in connections.get(auction_id, []):
                    await ws.send_json({
                        "type": "TIME_UPDATE",
                        "time_remaining": 0,
                        "current_end_time": now.isoformat(),
                        "status": "forced"
                    })
                break
            bid_data = {
                "auction_id": auction_id,
                "owner_email": user_email,
                "bid_amount": bid_amount,
                "freight_charges": freight,
                "origin_charges": origin,
                "destination_charges": dest,
                "transit_time": transit,
                "validity_period": validity,
                "bid_time": now,
            }
            bid = Bids(**bid_data)
            sql.add(bid)
            sql.commit()
            previous_best = highest.get(auction_id)
            if (
                auction_id not in highest or
                bid_amount < highest[auction_id]["bid_amount"]
            ):
                highest[auction_id] = bid_data

            if should_extend(auction, bid_data, previous_best):
                max_allowed = int(
                    (auction.forced_close_time - now).total_seconds()
                )
                time_remaining[auction_id] = min(
                    auction.extension_duration * 60,
                    max_allowed
                )
                current_end_time[auction_id] = now + timedelta(seconds=time_remaining[auction_id])
                for ws in connections.get(auction_id, []):
                    await ws.send_json({
                        "type": "TIME_UPDATE",
                        "time_remaining": time_remaining[auction_id],
                        "current_end_time": (now + timedelta(seconds=time_remaining[auction_id])).isoformat(),
                        "status": "active",
                        "monitoring": max_allowed <= 600
                    })
            def serialize(data):
                return {
                    **data,
                    "validity_period": data["validity_period"].isoformat()
                    if data["validity_period"]
                    else None,
                    "bid_time": data["bid_time"].isoformat(),
                }
            safe_bid = serialize(bid_data)
            safe_highest = serialize(highest[auction_id])
            dead = []
            for ws in connections.get(auction_id, []):
                try:
                    await ws.send_json({
                        "type": "UPDATE",
                        "highest": safe_highest,
                        "new_bid": safe_bid
                    })
                except:
                    dead.append(ws)
            for d in dead:
                connections[auction_id].remove(d)
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in connections.get(auction_id, []):
            connections[auction_id].remove(websocket)
        if auction_id in connections and not connections[auction_id]:
            del connections[auction_id]
        if auction_id in time_remaining and auction_id not in connections:
            del time_remaining[auction_id]
        if auction_id in current_end_time and auction_id not in connections:
            del current_end_time[auction_id]
        if auction_id in timer_tasks:
            timer_tasks[auction_id].cancel()
            del timer_tasks[auction_id]