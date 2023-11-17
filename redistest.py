import redis
db = redis.Redis()

db.rpush(f"waitClassID_123", 12345)

print(db.lpop(f"waitClassID_123"))