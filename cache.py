import os
from upstash_redis import Redis
import dotenv
dotenv.load_dotenv()

cache = Redis(
    url="https://charmed-flounder-97065.upstash.io",
    token=os.getenv("upstash")
)