from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_ollama import OllamaLLM
import pandas as pd

# ----------------------------
# Load Excel Data
# ----------------------------
print("🔄 Loading Excel file...")
df_orders = pd.read_excel(r"C:\Users\Aryan.Gaddadavara\Desktop\chatbot\excel_files\kfh_orders.xlsx")

df_orders["Customer ID"] = df_orders["Customer ID"].astype(str)
df_orders["Customer ID"] = df_orders["Customer ID"].str.replace(",", "").str.strip()
df_orders["Customer ID"] = df_orders["Customer ID"].str.replace(".0", "", regex=False)

print(f"✅ Loaded {len(df_orders)} rows from Excel\n")

# ----------------------------
# Initialize LLM
# ----------------------------
print("🔄 Initializing LLM...")
llm = OllamaLLM(model="phi3:mini-128k")
parser = JsonOutputParser()
print("✅ LLM Initialized\n")

# ----------------------------
# Intent Prompt
# ----------------------------
intent_prompt = PromptTemplate(
    template="""
You are an intent classifier for order queries.

Only choose from:
- order_status
- delivery_time
- rider_info

Return ONLY JSON:

{{
  "intent": "..."
}}

User Query:
{query}
""",
    input_variables=["query"]
)

intent_chain = intent_prompt | llm | parser

# ----------------------------
# STRICT Response Prompt (FIXED)
# ----------------------------
response_prompt = PromptTemplate(
    template="""
You are a customer support assistant.

Answer the user's question using ONLY the provided data.

Rules:
- Keep response SHORT (max 1–2 sentences)
- Be direct and clear
- Do NOT add extra details
- Do NOT assume anything
- Do NOT include instructions
- Do NOT output JSON

User Query:
{query}

Data:
{data}

Answer:
""",
    input_variables=["query", "data"]
)

response_chain = response_prompt | llm

# ----------------------------
# Get Latest Order
# ----------------------------
def get_latest_order(customer_id):
    print(f"\n🔍 Fetching orders for Customer ID: {customer_id}")

    user_orders = df_orders[df_orders["Customer ID"] == customer_id]

    print(f"📊 Found {len(user_orders)} orders")

    if user_orders.empty:
        print("❌ No orders found")
        return None

    latest_order = user_orders.sort_values(
        by="Order Date", ascending=False
    ).iloc[0]

    print(f"✅ Latest Order ID: {latest_order['Order ID']}")
    return latest_order

# ----------------------------
# Handle Query (Data Extraction)
# ----------------------------
def handle_query(intent, order_row):
    print(f"\n🧠 Handling intent: {intent}")

    if intent == "order_status":
        return {
            "Delivery Status": order_row["Delivery Status"]
        }

    elif intent == "delivery_time":
        return {
            "Delivery Date": order_row["Delivery Date"],
            "ETA": order_row["Eta"]
        }

    elif intent == "rider_info":
        return {
            "Rider": order_row["Rider"]
        }

    return None

# ----------------------------
# OPTIONAL: Rule-Based Response (More Stable)
# ----------------------------
def rule_based_response(intent, data):
    if intent == "order_status":
        return f"Your order is currently {data['Delivery Status']}."

    elif intent == "delivery_time":
        return f"Your order will be delivered on {data['Delivery Date']} and is expected around {data['ETA']}."

    elif intent == "rider_info":
        return f"Your delivery is being handled by {data['Rider']}."

    return None

# ----------------------------
# Chatbot Loop
# ----------------------------
print("🤖 Customer Care Bot (type 'exit' to quit)\n")

customer_id = input("Enter your Customer ID: ")
customer_id = customer_id.replace(",", "").strip()

while True:
    user_input = input("\nYou: ")

    if user_input.lower() in ["exit", "quit"]:
        print("Bot: Goodbye!")
        break

    try:
        # Step 1: Intent
        print("\n🔄 Step 1: Extracting intent...")
        result = intent_chain.invoke({"query": user_input})
        print("✅ Intent:", result)

        intent = result.get("intent")

        if intent not in ["order_status", "delivery_time", "rider_info"]:
            print("Bot: Sorry, I didn't understand your request.")
            continue

        # Step 2: Get Latest Order
        print("\n🔄 Step 2: Fetching latest order...")
        latest_order = get_latest_order(customer_id)

        if latest_order is None:
            print("Bot: No orders found.")
            continue

        # Step 3: Fetch Data
        print("\n🔄 Step 3: Fetching data...")
        data = handle_query(intent, latest_order)

        print("📊 Data:", data)

        if not data:
            print("Bot: No relevant data found.")
            continue

        # ----------------------------
        # Step 4 OPTION A: Rule-based (Recommended)
        # ----------------------------
        response = rule_based_response(intent, data)

        # ----------------------------
        # Step 4 OPTION B: LLM (fallback)
        # ----------------------------
        if not response:
            print("\n🔄 Generating response via LLM...")
            response = response_chain.invoke({
                "query": user_input,
                "data": str(data)
            })

        # Clean output
        response = str(response).strip()

        print("\n🤖 Bot:", response)

    except Exception as e:
        print("❌ Bot: Something went wrong.")
        print("Error:", e)