import os

import redis
import dotenv
dotenv.load_dotenv()

cache = redis.Redis(
    host='redis-12395.crce276.ap-south-1-3.ec2.cloud.redislabs.com',
    port=12395,
    decode_responses=True,
    username="default",
    password=os.getenv("REDIS_PASSWORD"),
)
