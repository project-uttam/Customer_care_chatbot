import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
from datetime import datetime

# ----------------------------
# LOAD ENV
# ----------------------------
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)


# ----------------------------
# TIME FORMAT FUNCTION
# ----------------------------
def format_time(timestamp):
    if pd.isna(timestamp):
        return None
    timestamp = pd.to_datetime(timestamp)
    return timestamp.strftime("%I:%M %p")

# ----------------------------
# FLEXIBLE TIME PARSER
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
# PARSE DELIVERY SLOT (FIXED)
# ----------------------------
def parse_slot(slot_str, current_time):
    start_str, end_str = slot_str.split(" to ")

    current_date = current_time.date()

    start_time = parse_time_flexible(start_str)
    end_time = parse_time_flexible(end_str)

    start_dt = datetime.combine(current_date, start_time)
    end_dt = datetime.combine(current_date, end_time)

    return start_dt, end_dt


# ----------------------------
# SLOT STATUS + PRIORITY
# ----------------------------
def get_slot_status_and_priority(slot_str, current_time):

    start_dt, end_dt = parse_slot(slot_str, current_time)

    # BEFORE SLOT
    if current_time < start_dt:
        return "BEFORE", None

    # AFTER SLOT (treat as high priority edge case if needed)
    if current_time > end_dt:
        return "AFTER", "1"

    # INSIDE SLOT
    total_duration = (end_dt - start_dt).total_seconds()
    elapsed = (current_time - start_dt).total_seconds()

    progress = elapsed / total_duration

    if progress < 0.5:
        return "INSIDE", "0"
    else:
        return "INSIDE", "1"


# ----------------------------
# INSERT PRIORITY
# ----------------------------
def insert_priority(order_id, status, priority_flag, current_time):

    order_id = int(order_id)

    check_query = text("""
        SELECT 1 FROM priority WHERE order_id = :order_id
    """)

    insert_query = text("""
        INSERT INTO priority (
            customer_request_source,
            current_order_status,
            order_id,
            request_time,
            priority_flag
        )
        VALUES (
            :source,
            :status,
            :order_id,
            :request_time,
            :priority_flag
        )
    """)

    with engine.connect() as conn:

        result = conn.execute(check_query, {"order_id": order_id}).fetchone()

        if result:
            return

        conn.execute(insert_query, {
            "source": "chatbot",
            "status": status,
            "order_id": order_id,
            "request_time": current_time,
            "priority_flag": priority_flag
        })

        conn.commit()


# ----------------------------
# FETCH ORDER
# ----------------------------
def fetch_order(order_id):

    order_id = int(order_id)

    query = """
        SELECT *
        FROM "Kfh_orders_7days"
        WHERE order_id = %s
    """

    df = pd.read_sql(query, engine, params=(order_id,))

    if df.empty:
        return None

    return df.iloc[0]


# ----------------------------
# FETCH 3PL
# ----------------------------
def get_3pl_data(order_id):

    order_id = int(order_id)

    query = """
        SELECT 
            rider_at_pickup,
            order_picked,
            rider_name,
            rider_assigned
        FROM "3PL_logs_7days"
        WHERE order_id = %s
    """

    df = pd.read_sql(query, engine, params=(order_id,))

    if df.empty:
        return None

    return df.iloc[0]


# ----------------------------
# LEFT BRANCH
# ----------------------------
def handle_left_branch(order):

    if pd.notna(order["picking_end_time"]):
        return f"Your order was packed at {format_time(order['picking_end_time'])}"

    if pd.notna(order["picking_start_time"]):
        return f"Your order packing started at {format_time(order['picking_start_time'])}"

    return "Your order is being prepared"


# ----------------------------
# RIGHT BRANCH
# ----------------------------
def handle_right_branch(order):

    order_id = int(order["order_id"])

    if pd.notna(order["order_pick_time"]):
        return f"Your order was picked at {format_time(order['order_pick_time'])}"

    if pd.notna(order["order_drop_time"]):

        drop_time_str = format_time(order["order_drop_time"])
        pl_data = get_3pl_data(order_id)

        if pl_data is not None:

            rider_name = pl_data.get("rider_name")

            if pl_data["order_picked"]:
                return f"Out for delivery with {rider_name}" if pd.notna(rider_name) else "Out for delivery"

            if pl_data["rider_at_pickup"]:
                return f"Rider arrived. Ready at {drop_time_str}"

            if pd.notna(rider_name):
                return f"Rider {rider_name} assigned. Ready at {drop_time_str}"

        return f"Order ready at {drop_time_str}"


# ----------------------------
# MAIN
# ----------------------------
def track_order(order_id, current_time):

    current_time = pd.to_datetime(current_time)

    order = fetch_order(order_id)

    if order is None:
        return "Order not found"

    slot = order["delivery_timeslot"]

    slot_status, priority_flag = get_slot_status_and_priority(slot, current_time)

    # 🚫 BEFORE SLOT BLOCK
    if slot_status == "BEFORE":
        return f"You have booked your timeslot from {slot}, so I can't provide order status right now."

    # ✅ NORMAL FLOW (INSIDE / AFTER)
    if pd.notna(order["order_drop_time"]):
        response = handle_right_branch(order)
    else:
        response = handle_left_branch(order)

    # 🔥 INSERT PRIORITY (ONLY WHEN INSIDE OR AFTER)
    insert_priority(order["order_id"], response, priority_flag, current_time)

    # 🎯 ADD LABEL
    if priority_flag == "P0":
        response += " | Normal Priority (P0)"
    elif priority_flag == "P1":
        response += " | ⚠️ High Priority (P1)"

    return response


# ----------------------------
# TEST
# ----------------------------
if __name__ == "__main__":
    order_id = 12177146
    current_time = "2026-04-30 20:05:00"  # test different times
    print(track_order(order_id, current_time))
