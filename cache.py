import redis

cache = redis.Redis(
    host='redis-12395.crce276.ap-south-1-3.ec2.cloud.redislabs.com',
    port=12395,
    decode_responses=True,
    username="default",
    password="cGVKA8ohAJJ2uDQjNBGYBRElDsyaFLRC",
)
