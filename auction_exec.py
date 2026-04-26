from datetime import datetime, timedelta
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from database import SessionLocal
from cache import cache
from models import Auction, Bids

auction_exec_router = APIRouter()

connections = {}
highest = {}
time_remaining = {}
timer_tasks = {}
current_end_time = {}


def refresh_auction_status(auction):
    with SessionLocal() as sql:
        now = datetime.utcnow() + timedelta(hours=5, minutes=30)

        bids = sql.query(Bids).filter(Bids.auction_id == auction.rfq_id).order_by(Bids.bid_time.asc()).all()
        
        current_close = auction.start_time + timedelta(minutes=auction.extension_duration)
        best_bid = None
        
        for b in bids:
            bid_data = {"bid_amount": b.bid_amount}
            if should_extend(auction, bid_data, best_bid):
                current_close = b.bid_time + timedelta(minutes=auction.extension_duration)
                
            if best_bid is None or b.bid_amount < best_bid["bid_amount"]:
                best_bid = bid_data

        effective_close = min(current_close, auction.forced_close_time)

        remaining = int((effective_close - now).total_seconds())

        if remaining <= 0:
            auction.status = 2 if effective_close == auction.forced_close_time else 0
            return auction.status, 0

        auction.status = 1
        return auction.status, remaining


@auction_exec_router.get("/{auction_id}")
async def get_auction(auction_id: int):
    with SessionLocal() as sql:
        auction = sql.query(Auction).filter(Auction.rfq_id == auction_id).first()
        if not auction:
            return {"success": False, "rfq": None}

        status, remaining = refresh_auction_status(auction)
        sql.commit()

        bids = sql.query(Bids).filter(Bids.auction_id == auction_id).all()
        now = datetime.utcnow() + timedelta(hours=5, minutes=30)

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
        return previous_best is None or new_bid["bid_amount"] < previous_best["bid_amount"]
    elif auction.trigger in (2, 3):
        return True
    return False


async def broadcast_time_update(auction_id, auction):
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    current_end = now + timedelta(seconds=time_remaining.get(auction_id, 0))
    current_end_time[auction_id] = current_end
    payload = {
        "type": "TIME_UPDATE",
        "current_end_time": current_end.isoformat(),
        "time_remaining": time_remaining.get(auction_id, 0),
        "status": auction.status
    }
    for conn in connections.get(auction_id, []):
        try:
            await conn.send_json(payload)
        except Exception:
            pass

async def timer_loop(auction_id: int):
    while auction_id in time_remaining:
        with SessionLocal() as sql:
            auction = sql.query(Auction).filter(Auction.rfq_id == auction_id).first()
            if not auction:
                break

            now = datetime.utcnow() + timedelta(hours=5, minutes=30)
            max_allowed = int((auction.forced_close_time - now).total_seconds())

            if max_allowed <= 0:
                auction.status = 2
                sql.commit()
                time_remaining[auction_id] = 0
                current_end_time[auction_id] = now
                await broadcast_time_update(auction_id, auction)
                break

            if time_remaining[auction_id] > max_allowed:
                time_remaining[auction_id] = max_allowed

            if time_remaining[auction_id] <= 0:
                auction.status = 0
                sql.commit()
                await broadcast_time_update(auction_id, auction)
                break

        time_remaining[auction_id] -= 1
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
        user_data = cache.hgetall(token) if token else None

        if not user_data:
            await websocket.close()
            return

        user_email = user_data.get("email")
        role = user_data.get("role")

        if not user_email or role not in ("supplier", "buyer"):
            await websocket.close()
            return

        with SessionLocal() as sql:
            auction = sql.query(Auction).filter(Auction.rfq_id == auction_id).first()
            if not auction:
                await websocket.close()
                return

            now = datetime.utcnow() + timedelta(hours=5, minutes=30)
            status, remaining = refresh_auction_status(auction)
            sql.commit()

        if auction_id not in time_remaining:
            time_remaining[auction_id] = remaining
            current_end_time[auction_id] = now + timedelta(seconds=remaining)

        if auction_id not in timer_tasks:
            timer_tasks[auction_id] = asyncio.create_task(timer_loop(auction_id))

        while True:
            res = await websocket.receive_json()

            if res.get("type") != "BID" or role != "supplier":
                continue

            try:
                now = datetime.utcnow() + timedelta(hours=5, minutes=30)

                # Parse validity_period safely
                vp_raw = res.get("validity_period", "")
                if vp_raw and isinstance(vp_raw, str) and vp_raw.strip():
                    validity_period = datetime.fromisoformat(vp_raw.strip())
                else:
                    validity_period = now

                with SessionLocal() as sql:
                    auction = sql.query(Auction).filter(Auction.rfq_id == auction_id).first()

                    if not auction or auction.status in (0, 2):
                        continue

                    bid = Bids(
                        auction_id=auction_id,
                        owner_email=user_email,
                        bid_amount=int(res["bid_amount"]),
                        freight_charges=int(res.get("freight_charges", 0)),
                        origin_charges=int(res.get("origin_charges", 0)),
                        destination_charges=int(res.get("destination_charges", 0)),
                        transit_time=int(res.get("transit_time", 0)),
                        bid_time=now,
                        validity_period=validity_period
                    )

                    sql.add(bid)
                    sql.commit()
                    sql.refresh(bid)

                    bid_data = {
                        "auction_id": auction_id,
                        "owner_email": user_email,
                        "bid_amount": bid.bid_amount,
                        "bid_time": now.isoformat(),
                    }

                    previous_best = highest.get(auction_id)
                    if not previous_best:
                        best_bid_db = sql.query(Bids).filter(Bids.auction_id == auction_id).order_by(Bids.bid_amount.asc()).first()
                        if best_bid_db:
                            previous_best = {
                                "auction_id": auction_id,
                                "owner_email": best_bid_db.owner_email,
                                "bid_amount": best_bid_db.bid_amount,
                                "bid_time": best_bid_db.bid_time.isoformat()
                            }
                            highest[auction_id] = previous_best

                    if auction_id not in highest or bid.bid_amount < highest[auction_id]["bid_amount"]:
                        highest[auction_id] = bid_data

                    if should_extend(auction, bid_data, previous_best):
                        max_allowed = int((auction.forced_close_time - now).total_seconds())
                        time_remaining[auction_id] = min(
                            auction.extension_duration * 60,
                            max_allowed
                        )
                        await broadcast_time_update(auction_id, auction)

                    update_payload = {
                        "type": "UPDATE",
                        "highest": highest[auction_id],
                        "new_bid": {
                            "bid_id": bid.bid_id,
                            "auction_id": bid.auction_id,
                            "owner_email": bid.owner_email,
                            "bid_amount": bid.bid_amount,
                            "bid_time": bid.bid_time.isoformat(),
                            "transit_time": bid.transit_time,
                            "freight_charges": bid.freight_charges,
                            "origin_charges": bid.origin_charges,
                            "destination_charges": bid.destination_charges,
                            "validity_period": bid.validity_period.isoformat() if bid.validity_period else None
                        }
                    }
                    for conn in connections.get(auction_id, []):
                        try:
                            await conn.send_json(update_payload)
                        except Exception:
                            pass

            except Exception as e:
                print(f"Error processing bid: {e}")
                continue

    except WebSocketDisconnect:
        pass

    finally:
        if websocket in connections.get(auction_id, []):
            connections[auction_id].remove(websocket)

        if auction_id in connections and not connections[auction_id]:
            connections.pop(auction_id, None)
            time_remaining.pop(auction_id, None)
            current_end_time.pop(auction_id, None)

            if auction_id in timer_tasks:
                timer_tasks[auction_id].cancel()
                timer_tasks.pop(auction_id, None)