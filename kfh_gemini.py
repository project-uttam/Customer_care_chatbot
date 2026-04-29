import os
import json
import re
from google import genai
from sqlalchemy import create_engine
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in .env file")

client = genai.Client(api_key=GOOGLE_API_KEY)

engine = create_engine(os.getenv("DATABASE_URL"))

def clean_customer_id(value):
    return int(str(value).replace(",", "").replace(".0", "").strip())

customer_memory = {}

# ----------------------------
# FETCH ORDERS
# ----------------------------
def get_recent_orders(customer_id):
    query = """
    SELECT 
        order_id,
        delivery_status,
        delivery_date,
        eta,
        rider,
        depo_name,
        delivery_timeslot,
        delivery_delay,
        order_date
    FROM kfh_orders
    WHERE customer_id = %s
    ORDER BY order_date DESC
    LIMIT 5;
    """
    return pd.read_sql(query, engine, params=(customer_id,))

# ----------------------------
# ORDER SELECTION FROM TEXT
# ----------------------------
def detect_order_selection(user_input, orders_df):
    text = user_input.lower()

    mapping = {
        "1": 0, "first": 0, "1st": 0,
        "2": 1, "second": 1, "2nd": 1,
        "3": 2, "third": 2, "3rd": 2
    }

    for key, idx in mapping.items():
        if key in text and idx < len(orders_df):
            return orders_df.iloc[idx]

    return None

# ----------------------------
# INTENT (BASE)
# ----------------------------
def get_intents(user_input):

    prompt = f"""
You are an intent extraction system.

Extract ALL relevant intents from the user query.

Return STRICT JSON:
{{"intents": []}}

Allowed intents:
- order_status
- delivery_timeslot
- delivery_time
- rider_info
- order_location
- delivery_delay
- full_order_details

Examples:
User: my order is late
Output: {{"intents": ["delivery_delay"]}}

User: what is the timeslot and status
Output: {{"intents": ["delivery_timeslot", "order_status"]}}

User: tell me everything about my order
Output: {{"intents": ["full_order_details"]}}

Rules:
- Return multiple intents if needed
- Do NOT explain anything

User Query:
{user_input}
"""

    try:
        res = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt
        )

        text = res.text.strip().replace("```json", "").replace("```", "")
        parsed = json.loads(text)
        return parsed.get("intents", [])

    except:
        return []

# ----------------------------
# CONTEXT INTENTS
# ----------------------------
def get_context_intents(user_input, memory):

    text = user_input.lower()

    # 🔥 HARD OVERRIDE (MOST IMPORTANT)
    if any(word in text for word in ["everything", "all details", "full details", "complete"]):
        return ["full_order_details"]

    current = get_intents(user_input)

    if current:
        return current

    # fallback
    for chat in reversed(memory["history"]):
        if chat["intents"]:
            return chat["intents"]

    return []

# ----------------------------
# FORMAT HISTORY
# ----------------------------
def format_history(memory):
    history = memory["history"][-3:]
    return "\n".join([f"User: {c['user']}\nBot: {c['bot']}" for c in history])

# ----------------------------
# DATA EXTRACTION
# ----------------------------
def extract_data(intent, order):

    oid = order['order_id']
    rider = order['rider'] if pd.notna(order['rider']) else "Not assigned"

    if intent == "order_status":
        return f"Order ID {oid} is {order['delivery_status']}"

    elif intent == "delivery_time":
        return f"Order ID {oid} will be delivered on {order['delivery_date']} with ETA {order['eta']} minutes"
    
    elif intent == "delivery_timeslot":
        return f"Order ID {oid} is scheduled for {order['delivery_timeslot']}"

    elif intent == "rider_info":
        return f"Order ID {oid} rider is {rider}"

    elif intent == "order_location":
        return f"Order ID {oid} is coming from {order['depo_name']} warehouse"

    elif intent == "delivery_delay":
        delay = order['delivery_delay']
        if pd.isna(delay):
            return f"Order ID {oid} has no delay information available"
        return f"Order ID {oid} is delayed by {delay} minutes"

    elif intent == "full_order_details":

        delay = order['delivery_delay']
        delay_text = f"{delay} minutes" if pd.notna(delay) else "Not available"

        return (
            f"Order ID {oid} details:\n"
            f"- Status: {order['delivery_status']}\n"
            f"- Delivery Date: {order['delivery_date']}\n"
            f"- Timeslot: {order['delivery_timeslot']}\n"
            f"- ETA: {order['eta']} minutes\n"
            f"- Rider: {rider}\n"
            f"- Warehouse: {order['depo_name']}\n"
            f"- Delay: {delay_text}"
        )

    return None

# ----------------------------
# RESPONSE GENERATOR
# ----------------------------
def summarize_response(user_input, data, memory):

    prompt = f"""
Conversation:
{format_history(memory)}

User: {user_input}

Data:
{data}

Make a short polite response.
"""

    try:
        res = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt
        )
        return res.text.strip()
    except:
        return data

# ----------------------------
# COMPLEX QUERY
# ----------------------------
def handle_complex_query(user_input, order, memory):

    oid = order['order_id']

    prompt = f"""
Conversation:
{format_history(memory)}

User: {user_input}

Order:
ID: {oid}
Status: {order['delivery_status']}
Date: {order['delivery_date']}
ETA: {order['eta']}

Answer clearly.
"""

    try:
        res = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt
        )
        return res.text.strip()
    except:
        return "Not available"

# ----------------------------
# MAIN LOOP
# ----------------------------
def main():

    print("🤖 Gemini Customer Care Bot\n")

    customer_id = clean_customer_id(input("Enter Customer ID: "))

    if customer_id not in customer_memory:
        customer_memory[customer_id] = {
            "history": [],
            "selected_order": None,
            "orders_df": None
        }

    while True:

        user_input = input("\nYou: ").strip()

        if user_input.lower() in ["exit", "quit"]:
            print("Bot: Goodbye!")
            break

        try:

            memory = customer_memory[customer_id]

            if memory["orders_df"] is None:
                memory["orders_df"] = get_recent_orders(customer_id)

            orders_df = memory["orders_df"]

            if orders_df.empty:
                print("Bot: No orders found.")
                continue

            # WHICH ORDER
            if "which order" in user_input.lower():
                if memory["selected_order"] is not None:
                    print(f"Bot: I am referring to Order ID {memory['selected_order']['order_id']}")
                else:
                    print("Bot: No order selected yet.")
                continue

            # SWITCH ORDER
            detected = detect_order_selection(user_input, orders_df)

            if detected is not None:
                memory["selected_order"] = detected
                print(f"Bot: Now referring to Order ID {detected['order_id']}")
                continue

            # SELECT ORDER
            if memory["selected_order"] is None:

                if len(orders_df) == 1:
                    memory["selected_order"] = orders_df.iloc[0]

                else:
                    print("\nBot: Select an order:")
                    for i, row in orders_df.iterrows():
                        print(f"{i+1}. Order {row['order_id']} | {row['order_date']}")

                    choice = input("Enter number: ")

                    try:
                        memory["selected_order"] = orders_df.iloc[int(choice)-1]
                    except:
                        print("Invalid choice")
                        continue

            order = memory["selected_order"]

            # 🔥 INTENTS
            intents = get_context_intents(user_input, memory)
            print("🧠 Intents:", intents)

            # 🔥 PRIORITY: FULL DETAILS
            if "full_order_details" in intents:
                final_response = extract_data("full_order_details", order)
                print("\n🤖 Bot:", final_response)

            else:
                responses = []

                for intent in intents:
                    r = extract_data(intent, order)
                    if r:
                        responses.append(r)

                if len(responses) == 1:
                    final_response = responses[0]

                elif len(responses) > 1:
                    final_response = summarize_response(user_input, " | ".join(responses), memory)

                else:
                    final_response = handle_complex_query(user_input, order, memory)

                print("\n🤖 Bot:", final_response)

            # SAVE MEMORY
            memory["history"].append({
                "user": user_input,
                "bot": final_response,
                "intents": intents
            })

            if len(memory["history"]) > 20:
                memory["history"].pop(0)

        except Exception as e:
            print("❌ Error:", str(e))


if __name__ == "__main__":
    main()
