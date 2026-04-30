# import pandas as pd
# from sqlalchemy import create_engine, text
# import os
# from dotenv import load_dotenv
# from datetime import datetime

# # ----------------------------
# # LOAD ENV
# # ----------------------------
# load_dotenv()

# DATABASE_URL = os.getenv("DATABASE_URL")

# engine = create_engine(DATABASE_URL)


# # ----------------------------
# # TIME FORMAT FUNCTION
# # ----------------------------
# def format_time(timestamp):
#     if pd.isna(timestamp):
#         return None

#     timestamp = pd.to_datetime(timestamp)
#     return timestamp.strftime("%I:%M %p")


# # ----------------------------
# # INSERT PRIORITY FUNCTION
# # ----------------------------
# def insert_priority(order_id, status):

#     order_id = int(order_id)  # ✅ FIX

#     check_query = text("""
#         SELECT 1 FROM priority WHERE order_id = :order_id
#     """)

#     insert_query = text("""
#         INSERT INTO priority (
#             customer_request_source,
#             current_order_status,
#             order_id,
#             request_time,
#             priority_flag
#         )
#         VALUES (
#             :source,
#             :status,
#             :order_id,
#             :request_time,
#             :priority_flag
#         )
#     """)

#     with engine.connect() as conn:

#         result = conn.execute(check_query, {"order_id": order_id}).fetchone()

#         if result:
#             return

#         conn.execute(insert_query, {
#             "source": "chatbot",
#             "status": status,
#             "order_id": order_id,
#             "request_time": datetime.now(),
#             "priority_flag": 1
#         })

#         conn.commit()


# # ----------------------------
# # FETCH ORDER DATA
# # ----------------------------
# def fetch_order(order_id):

#     order_id = int(order_id)  # ✅ FIX

#     query = """
#         SELECT *
#         FROM kfh_orders_7_days
#         WHERE order_id = %s
#     """

#     df = pd.read_sql(query, engine, params=(order_id,))

#     if df.empty:
#         return None

#     return df.iloc[0]


# # ----------------------------
# # FETCH 3PL DATA
# # ----------------------------
# def get_3pl_data(order_id):

#     order_id = int(order_id)  # ✅ FIX

#     query = """
#         SELECT 
#             "rider_at_pickup",
#             "order_picked",
#             "rider_name",
#             rider_assigned
#         FROM "3PL_7_Days"
#         WHERE "order_id" = %s
#     """

#     df = pd.read_sql(query, engine, params=(order_id,))

#     if df.empty:
#         return None

#     return df.iloc[0]


# # ----------------------------
# # GLOBAL PRIORITY CHECK
# # ----------------------------
# def check_and_insert_priority(order):

#     order_id = int(order["order_id"])  # ✅ FIX

#     pl_data = get_3pl_data(order_id)

#     rider_assigned = None

#     if pl_data is not None:
#         rider_assigned = pl_data.get("rider_assigned")

#     # 🚨 GLOBAL CONDITION
#     if not rider_assigned:
#         insert_priority(
#             order_id,
#             "Rider not assigned"
#         )
#         return True

#     return False


# # ----------------------------
# # LEFT BRANCH (PACKING)
# # ----------------------------
# def handle_left_branch(order):

#     if pd.notna(order["picking_end_time"]):
#         time_str = format_time(order["picking_end_time"])
#         return f"Your order was packed at {time_str} and will be moved shortly"

#     if pd.notna(order["picking_start_time"]):
#         time_str = format_time(order["picking_start_time"])
#         return f"Your order packing started at {time_str} and is currently in progress"

#     return "Your order is being prepared"


# # ----------------------------
# # RIGHT BRANCH (POST PACKING)
# # ----------------------------
# def handle_right_branch(order):

#     order_id = int(order["order_id"])  # ✅ FIX

#     # 🚴 Picked
#     if pd.notna(order["order_pick_time"]):
#         time_str = format_time(order["order_pick_time"])
#         return f"Your order was picked at {time_str} and is out for delivery"

#     # 📦 Dropped
#     if pd.notna(order["order_drop_time"]):

#         drop_time_str = format_time(order["order_drop_time"])
#         pl_data = get_3pl_data(order_id)

#         if pl_data is not None:

#             rider_name = pl_data.get("Rider Name")

#             # 🚴 Picked via 3PL
#             if pl_data["Order Picked"]:
#                 if pd.notna(rider_name) and rider_name != "":
#                     return f"Your order has been picked and is out for delivery with {rider_name}"
#                 else:
#                     return "Your order has been picked and is out for delivery"

#             # 📍 Rider at pickup
#             if pl_data["Rider At Pickup"]:
#                 return f"Rider has arrived. Your order was ready at {drop_time_str} and will be picked shortly"

#             # 🧍 Rider assigned
#             if pd.notna(rider_name) and rider_name != "":
#                 return f"Rider {rider_name} has been assigned. Your order was ready at {drop_time_str}"

#         return f"Your order is ready at {drop_time_str}"


# # ----------------------------
# # MAIN FUNCTION
# # ----------------------------
# def track_order(order_id):

#     order_id = int(order_id)  # ✅ FIX

#     order = fetch_order(order_id)

#     if order is None:
#         return "Order not found"

#     # 🚨 GLOBAL PRIORITY CHECK
#     is_priority = check_and_insert_priority(order)

#     # Branching
#     if pd.notna(order["order_drop_time"]):
#         response = handle_right_branch(order)
#     else:
#         response = handle_left_branch(order)

#     # Append priority message
#     if is_priority:
#         response += " | ⚠️ This order has been marked as PRIORITY."

#     return response


# # ----------------------------
# # TEST
# # ----------------------------
# if __name__ == "__main__":
#     order_id = 12178635
#     result = track_order(order_id)
#     print(result)



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
# PARSE DELIVERY SLOT
# ----------------------------
def parse_slot(slot_str, current_time):
    start_str, end_str = slot_str.split(" to ")

    current_date = current_time.date()

    start_time = datetime.strptime(start_str, "%I:%M %p").time()
    end_time = datetime.strptime(end_str, "%I:%M %p").time()

    start_dt = datetime.combine(current_date, start_time)
    end_dt = datetime.combine(current_date, end_time)

    return start_dt, end_dt


# ----------------------------
# CALCULATE PRIORITY FLAG
# ----------------------------
def calculate_priority_flag(slot_str, current_time):

    start_dt, end_dt = parse_slot(slot_str, current_time)

    # BEFORE SLOT
    if current_time < start_dt:
        return 0

    # AFTER SLOT
    if current_time > end_dt:
        return 0

    # INSIDE SLOT
    total_duration = (end_dt - start_dt).total_seconds()
    elapsed = (current_time - start_dt).total_seconds()

    progress = elapsed / total_duration

    if progress < 0.5:
        return 1
    else:
        return 0


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
            "request_time": current_time,  # ✅ use passed time
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
        FROM kfh_orders_7_days
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
        FROM "3PL_7_Days"
        WHERE order_id = %s
    """

    df = pd.read_sql(query, engine, params=(order_id,))

    if df.empty:
        return None

    return df.iloc[0]


# ----------------------------
# PRIORITY CHECK
# ----------------------------
def check_and_insert_priority(order, current_time):

    order_id = int(order["order_id"])
    slot = order["delivery_timeslot"]

    priority_flag = calculate_priority_flag(slot, current_time)

    pl_data = get_3pl_data(order_id)
    rider_assigned = None

    if pl_data is not None:
        rider_assigned = pl_data.get("rider_assigned")

    if not rider_assigned:
        insert_priority(order_id, "Rider not assigned", priority_flag, current_time)
        return priority_flag

    return None


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

    current_time = pd.to_datetime(current_time)  # ✅ convert once

    order = fetch_order(order_id)

    if order is None:
        return "Order not found"

    priority_flag = check_and_insert_priority(order, current_time)

    if pd.notna(order["order_drop_time"]):
        response = handle_right_branch(order)
    else:
        response = handle_left_branch(order)

    if priority_flag == 1:
        response += " | ⚠️ High Priority"
    elif priority_flag == 0:
        response += " | Normal Priority"

    return response


# ----------------------------
# TEST
# ----------------------------
if __name__ == "__main__":
    order_id = 12178388
    current_time = "2026-04-30 15:58:08"  # ✅ YOU CONTROL TIME
    print(track_order(order_id, current_time))