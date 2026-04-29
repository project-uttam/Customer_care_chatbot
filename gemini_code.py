import os
import json
from google import genai
from sqlalchemy import create_engine
import pandas as pd
from dotenv import load_dotenv

# ----------------------------
# LOAD ENV VARIABLES
# ----------------------------
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in .env file")

# ----------------------------
# CONFIG GEMINI
# ----------------------------
client = genai.Client(api_key=GOOGLE_API_KEY)

# ----------------------------
# DB CONNECTION
# ----------------------------
engine = create_engine(
    os.getenv("DATABASE_URL")
)

# ----------------------------
# CLEAN ID
# ----------------------------
def clean_customer_id(value):
    return int(str(value).replace(",", "").replace(".0", "").strip())

# ----------------------------
# CACHE
# ----------------------------
order_cache = {}

# ----------------------------
# FETCH ORDER
# ----------------------------
def get_latest_order(customer_id):

    if customer_id in order_cache:
        return order_cache[customer_id]

    query = """
    SELECT 
        order_id,
        delivery_status,
        delivery_date,
        eta,
        rider,
        depo_name,
        delivery_timeslot,
        delivery_delay
    FROM orders
    WHERE customer_id = %s
    ORDER BY order_date DESC
    LIMIT 1;
    """

    df = pd.read_sql(query, engine, params=(customer_id,))

    if df.empty:
        return None

    order = df.iloc[0]
    order_cache[customer_id] = order
    return order

# ----------------------------
# MULTI-INTENT EXTRACTION (Gemini)
# ----------------------------
def get_intents(user_input):

    prompt = f"""
You are an intent extraction system.

Extract ALL relevant intents from the user query.

Return STRICT JSON format:
{{
  "intents": ["intent1", "intent2"]
}}

Allowed intents:
- order_status
- delivery_time
- rider_info
- order_location
- delivery_delay

Rules:
- Return multiple intents if needed
- If unsure, return empty list
- Do NOT explain anything

User Query:
{user_input}
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt
        )

        text = response.text.strip()
        text = text.replace("```json", "").replace("```", "")

        parsed = json.loads(text)
        return parsed.get("intents", [])

    except Exception as e:
        print("Intent Error:", e)
        return []

# ----------------------------
# RULE-BASED EXTRACTION
# ----------------------------
def extract_data(intent, order):

    rider = order['rider'] if pd.notna(order['rider']) else "Not assigned"

    if intent == "order_status":
        return f"Delivery status is {order['delivery_status']}"

    elif intent == "delivery_time":
        return f"Delivery on {order['delivery_date']} with ETA {order['eta']} minutes"

    elif intent == "rider_info":
        return f"Rider assigned is {rider}"

    elif intent == "order_location":
        return f"Order is coming from {order['depo_name']} warehouse"

    elif intent == "delivery_delay":
        return f"Delivery delay is {order['delivery_delay']} minutes"

    return None

# ----------------------------
# RESPONSE GENERATOR (Gemini)
# ----------------------------
def summarize_response(user_input, data):

    prompt = f"""
You are a professional customer care assistant.

Convert the data into a natural, polite response.

Rules:
- 1–2 short sentences
- Friendly tone
- Do NOT add extra info

User Query:
{user_input}

Data:
{data}

Response:
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip()

    except Exception:
        return data

# ----------------------------
# COMPLEX FALLBACK (Gemini)
# ----------------------------
def handle_complex_query(user_input, order):

    full_data = f"""
    Status: {order['delivery_status']}
    Delivery Date: {order['delivery_date']}
    ETA: {order['eta']} minutes
    Rider: {order['rider']}
    Warehouse: {order['depo_name']}
    Delay: {order['delivery_delay']} minutes
    """

    prompt = f"""
Answer the user's question using ONLY this data.

User Query:
{user_input}

Order Data:
{full_data}

Rules:
- Be short and clear
- Do NOT guess
- If data missing, say not available

Response:
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt
        )
        return response.text.strip()

    except Exception:
        return "Sorry, I couldn't process your request."

# ----------------------------
# CHATBOT LOOP
# ----------------------------
def main():

    print("🤖 Gemini Customer Care Bot\n")

    customer_id = clean_customer_id(input("Enter Customer ID: "))

    while True:

        user_input = input("\nYou: ")

        if user_input.lower() in ["exit", "quit"]:
            print("Bot: Goodbye!")
            break

        try:

            # STEP 1: MULTI-INTENT
            intents = get_intents(user_input)
            print("🧠 Intents:", intents)

            # STEP 2: FETCH DATA
            order = get_latest_order(customer_id)

            if order is None:
                print("Bot: No orders found.")
                continue

            # STEP 3: RULE EXTRACTION
            responses = []

            for intent in intents:
                res = extract_data(intent, order)
                if res:
                    responses.append(res)

            # STEP 4: RESPONSE LOGIC
            if len(responses) == 1:
                final_response = responses[0]   # ⚡ skip LLM

            elif len(responses) > 1:
                combined = " | ".join(responses)
                final_response = summarize_response(user_input, combined)

            else:
                final_response = handle_complex_query(user_input, order)

            print("\n🤖 Bot:", final_response)

        except Exception as e:
            print("❌ Error:", str(e))


# ----------------------------
# RUN
# ----------------------------
if __name__ == "__main__":
    main()