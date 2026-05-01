import datetime as dt

s = dt.datetime.now()
from fastapi import FastAPI, Request, Response, WebSocket

app = FastAPI()


@app.get("/")
async def test(req: Request):
    data = await req.json()
    print(data)
    return {"hello world": "how are you"}
