# Uploading the data into the redis 

import pandas as pd
import redis
import json
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

# ----------------------------
# LOAD ENV VARIABLES
# ----------------------------
load_dotenv()

# PostgreSQL connection
engine = create_engine(
    os.getenv("DATABASE_URL")
)

# Redis connection
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True
)

# ----------------------------
# LOAD DATA FROM DATABASE
# ----------------------------
df = pd.read_sql('SELECT * FROM "orders"', engine)

print("Original columns:", df.columns.tolist())

# ----------------------------
# CLEAN COLUMN NAMES
# ----------------------------
df.columns = (
    df.columns
    .str.strip()
    .str.lower()
    .str.replace(" ", "_")
)

print("Cleaned columns:", df.columns.tolist())

# ----------------------------
# SORT DATA (latest order last)
# ----------------------------
if "order_date" in df.columns:
    df = df.sort_values("order_date")

# ----------------------------
# LOAD INTO REDIS
# ----------------------------
count = 0

for _, row in df.iterrows():

    # ✅ direct access (safe + correct)
    customer_id = row["customer_id"]

    # skip invalid rows
    if pd.isna(customer_id):
        continue

    # normalize fields for chatbot
    mapped_data = {
        "order_id": row.get("order_id"),
        "customer_id": int(customer_id),

        "delivery_status": row.get("delivery_status"),
        "delivery_date": str(row.get("delivery_date")),
        "delivery_time": row.get("delivery_time"),
        "delivery_timeslot": row.get("delivery_timeslot"),

        "rider": row.get("rider"),
        "warehouse": row.get("depo_name"),

        "delivery_delay": row.get("delivery_delay"),
        "eta": row.get("eta")
    }

    # correct Redis key
    redis_key = f"Customer:{int(customer_id)}"

    redis_client.set(
        redis_key,
        json.dumps(mapped_data, default=str)
    )

    count += 1

print(f"✅ {count} records loaded into Redis successfully!")

# Clearing the redis cache 
import redis

r = redis.Redis(host="localhost", port=6379, db=0)

r.flushdb()
print("✅ Redis cleared")





# Extracting the data 
import redis
import json

r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

customer_id = 1184882
key = f"Customer:{customer_id}"

data = r.get(key)

if data:
    print("🔑 Key:", key)
    
    parsed = json.loads(data)

    print("\n📦 Full Data:")
    for k, v in parsed.items():
        print(f"{k}: {v}")
else:
    print("❌ No data found")




# Checking the keys
import redis

r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

keys = r.keys("*")
print("Total keys:", len(keys))
print("Sample keys:", keys[:10])