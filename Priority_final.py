import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
from datetime import datetime
from urllib.parse import quote_plus

# ----------------------------
# LOAD ENV
# ----------------------------
print("🔄 Loading environment variables...")
load_dotenv()

LIVE_DB_HOST = os.getenv("DB_HOST")
LIVE_DB_NAME = os.getenv("DB_NAME")
LIVE_DB_USER = os.getenv("DB_USER")
LIVE_DB_PASSWORD = os.getenv("DB_PASSWORD")
LIVE_DB_PORT = os.getenv("DB_PORT")

LIVE_DATABASE_URL = f"postgresql://{LIVE_DB_USER}:{quote_plus(LIVE_DB_PASSWORD)}@{LIVE_DB_HOST}:{LIVE_DB_PORT}/{LIVE_DB_NAME}"
LOCAL_DATABASE_URL = os.getenv("DATABASE_URL")

live_engine = create_engine(LIVE_DATABASE_URL)
local_engine = create_engine(LOCAL_DATABASE_URL)

print("✅ Live DB connected (READ)")
print("✅ Local DB connected (WRITE)")


# ----------------------------
# DEBUG HELPER
# ----------------------------
def debug_col(name, value):
    if pd.isna(value):
        print(f"   ❌ {name} = NULL")
    else:
        print(f"   ✅ {name} = {value}")


# ----------------------------
# TIME FORMAT
# ----------------------------
def format_time(timestamp):
    if pd.isna(timestamp):
        return None
    return pd.to_datetime(timestamp).strftime("%I:%M %p")


# ----------------------------
# TIME PARSER
# ----------------------------
def parse_time_flexible(t_str):
    t_str = t_str.strip()
    for fmt in ("%I:%M %p", "%I %p", "%H:%M"):
        try:
            return datetime.strptime(t_str, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Invalid time format: {t_str}")


# ----------------------------
# PARSE SLOT
# ----------------------------
def parse_slot(slot_str, current_time):
    print(f"🕒 Parsing slot: {slot_str}")

    start_str, end_str = slot_str.split(" to ")
    current_date = current_time.date()

    start_dt = datetime.combine(current_date, parse_time_flexible(start_str))
    end_dt = datetime.combine(current_date, parse_time_flexible(end_str))

    print(f"   ➤ Start: {start_dt}, End: {end_dt}")
    return start_dt, end_dt


# ----------------------------
# SLOT STATUS
# ----------------------------
def get_slot_status_and_priority(slot_str, current_time):

    print(f"🧾 Raw Slot Value: {slot_str}")

    start_dt, end_dt = parse_slot(slot_str, current_time)

    if current_time < start_dt:
        print("📍 BEFORE SLOT → blocked")
        return "BEFORE", None

    if current_time > end_dt:
        print("📍 AFTER SLOT → HIGH PRIORITY")
        return "AFTER", "1"

    total = (end_dt - start_dt).total_seconds()
    elapsed = (current_time - start_dt).total_seconds()
    progress = elapsed / total

    print(f"📍 INSIDE SLOT | Progress: {round(progress*100,2)}%")

    if progress < 0.5:
        print("➡️ First half → NORMAL priority")
        return "INSIDE", "0"
    else:
        print("➡️ Second half → HIGH priority")
        return "INSIDE", "1"


# ----------------------------
# INSERT PRIORITY
# ----------------------------
def insert_priority(order_id, status, priority_flag, current_time):

    print(f"📝 Writing to LOCAL DB")

    order_id = int(order_id)

    check_query = text("SELECT 1 FROM priority WHERE order_id = :order_id")

    insert_query = text("""
        INSERT INTO priority (
            customer_request_source,
            current_order_status,
            order_id,
            request_time,
            priority_flag
        )
        VALUES (:source, :status, :order_id, :request_time, :priority_flag)
    """)

    with local_engine.connect() as conn:

        if conn.execute(check_query, {"order_id": order_id}).fetchone():
            print("⚠️ Already exists")
            return

        conn.execute(insert_query, {
            "source": "chatbot",
            "status": status,
            "order_id": order_id,
            "request_time": current_time,
            "priority_flag": priority_flag
        })

        conn.commit()
        print("✅ Inserted into priority")


# ----------------------------
# FETCH ORDER
# ----------------------------
def fetch_order(order_id):

    print(f"🌐 Fetching order {order_id}")

    query = """SELECT * FROM "kfh_orders" WHERE order_id = %s"""

    df = pd.read_sql(query, live_engine, params=(order_id,))

    if df.empty:
        print("❌ Order not found")
        return None

    print("✅ Order fetched")
    return df.iloc[0]


# ----------------------------
# FETCH ORDERS BY CUSTOMER
# ----------------------------
def fetch_orders_by_customer(customer_id):

    print(f"🌐 Fetching orders for customer {customer_id}")

    query = """SELECT order_id FROM "kfh_orders" WHERE customer_id = %s"""

    df = pd.read_sql(query, live_engine, params=(customer_id,))

    if df.empty:
        print("❌ No orders")
        return []

    order_ids = [int(x) for x in df["order_id"].tolist()]
    print(f"✅ Orders: {order_ids}")
    return order_ids


# ----------------------------
# FETCH 3PL
# ----------------------------
def get_3pl_data(order_id):

    print(f"🌐 Fetching 3PL data")

    query = """
        SELECT rider_at_pickup, order_picked, rider_name
        FROM "kfh_3pl_logs"
        WHERE order_id = %s
    """

    df = pd.read_sql(query, live_engine, params=(order_id,))

    if df.empty:
        print("⚠️ No 3PL data")
        return None

    print("✅ 3PL data fetched")
    return df.iloc[0]


# ----------------------------
# LEFT BRANCH
# ----------------------------
def handle_left_branch(order):

    print("📦 LEFT BRANCH")

    debug_col("picking_start_time", order["picking_start_time"])
    debug_col("picking_end_time", order["picking_end_time"])

    if pd.notna(order["picking_end_time"]):
        print("➡️ Packed")
        return f"Your order was packed at {format_time(order['picking_end_time'])}"

    if pd.notna(order["picking_start_time"]):
        print("➡️ Packing started")
        return f"Your order packing started at {format_time(order['picking_start_time'])}"

    print("➡️ Still preparing")
    return "Your order is being prepared"


# ----------------------------
# RIGHT BRANCH
# ----------------------------
def handle_right_branch(order):

    print("🚚 RIGHT BRANCH (Clean Logic)")

    order_id = int(order["order_id"])

    # 🔍 Debug columns
    debug_col("order_pick_time", order["order_pick_time"])
    debug_col("order_drop_time", order["order_drop_time"])
    debug_col("rider (orders)", order.get("rider"))

    # ----------------------------
    # ✅ STEP 1: ORDER PICKED
    # ----------------------------
    if pd.notna(order["order_pick_time"]):

        print("➡️ Condition: order_pick_time NOT NULL → ORDER PICKED")

        rider_name = order.get("rider")

        if pd.notna(rider_name):
            print("➡️ Rider found in orders table")
            return f"Your order was picked at {format_time(order['order_pick_time'])} and is out for delivery with {rider_name}"
        else:
            print("➡️ Rider missing in orders → fallback to 3PL")

            pl_data = get_3pl_data(order_id)

            if pl_data is not None and pd.notna(pl_data.get("rider_name")):
                return f"Your order was picked at {format_time(order['order_pick_time'])} and is out for delivery with {pl_data['rider_name']}"

            return f"Your order was picked at {format_time(order['order_pick_time'])}"

    # ----------------------------
    # ❗ STEP 2: NOT PICKED → CHECK 3PL
    # ----------------------------
    print("➡️ Condition: order_pick_time NULL → checking 3PL")

    drop_time = format_time(order["order_drop_time"]) if pd.notna(order["order_drop_time"]) else None

    pl_data = get_3pl_data(order_id)

    if pl_data is not None:

        debug_col("3PL.order_picked", pl_data["order_picked"])
        debug_col("3PL.rider_at_pickup", pl_data["rider_at_pickup"])
        debug_col("3PL.rider_name", pl_data["rider_name"])

        # 🚚 Out for delivery
        if pl_data["order_picked"]:
            print("➡️ 3PL.order_picked TRUE → OUT FOR DELIVERY")
            return f"Out for delivery with {pl_data['rider_name']}" if pd.notna(pl_data["rider_name"]) else "Out for delivery"

        # 📍 Rider arrived
        if pl_data["rider_at_pickup"]:
            print("➡️ 3PL.rider_at_pickup TRUE → RIDER ARRIVED")
            return f"Rider arrived. Order ready at {drop_time}" if drop_time else "Rider arrived"

        # 🧑‍✈️ Rider assigned
        if pd.notna(pl_data["rider_name"]):
            print("➡️ 3PL.rider_name NOT NULL → RIDER ASSIGNED")
            return f"Rider {pl_data['rider_name']} assigned. Order ready at {drop_time}" if drop_time else f"Rider {pl_data['rider_name']} assigned"

    # ----------------------------
    # ❌ STEP 3: NO RIDER INFO
    # ----------------------------
    print("➡️ No rider info anywhere")

    if drop_time:
        return f"Order ready at {drop_time}. Rider will be assigned shortly"

    return "Rider will be assigned shortly"


# ----------------------------
# TRACK ORDER
# ----------------------------
def track_order(order_id):

    print("\n🚀 Tracking Order:", order_id)

    current_time = pd.to_datetime(datetime.now())
    print(f"🕒 Current Time: {current_time}")

    order = fetch_order(order_id)
    if order is None:
        return "Order not found"

    slot_status, priority_flag = get_slot_status_and_priority(order["delivery_timeslot"], current_time)

    debug_col("order_drop_time", order["order_drop_time"])

    if slot_status == "BEFORE":
        return "Too early to show status"

    if pd.notna(order["order_drop_time"]):
        print("➡️ Going RIGHT")
        response = handle_right_branch(order)
    else:
        print("➡️ Going LEFT")
        response = handle_left_branch(order)

    insert_priority(order["order_id"], response, priority_flag, current_time)

    if priority_flag == "0":
        response += " | P0"
    elif priority_flag == "1":
        response += " | ⚠️ P1"

    print("✅ Final:", response)
    return response


# ----------------------------
# CUSTOMER FLOW
# ----------------------------
def track_order_by_customer(customer_id):

    order_ids = fetch_orders_by_customer(customer_id)

    if not order_ids:
        return "No orders found"

    if len(order_ids) > 1:
        print("Multiple orders:", order_ids)
        order_id = int(input("Select Order ID: "))
    else:
        order_id = order_ids[0]

    return track_order(order_id)


# ----------------------------
# TEST
# ----------------------------
if __name__ == "__main__":
    cid = int(input("Enter Customer ID: "))
    print(track_order_by_customer(cid))