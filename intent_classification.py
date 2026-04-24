# from langchain_core.prompts import PromptTemplate
# from langchain_core.output_parsers import JsonOutputParser
# from langchain_ollama import OllamaLLM
# import json

# llm = OllamaLLM(
#     model="phi3:mini",       # Switch from 128k variant
#     temperature=0,
#     num_predict=150,
#     num_ctx=2048,
#     streaming=True,
# )
# parser = JsonOutputParser()

# # ─── All supported intent categories ──────────────────────────────────────────
# INTENT_CATEGORIES = """
# ORDER INTENTS:....
# """

# # ─── Table mapping ─────────────────────────────────────────────────────────────
# TABLE_MAP = """
# Available database tables and their purpose:
# 1. kfh_orders:
#    - Order tracking, delivery status, logistics, rider assignment

# 2. tbl_customerorderdetails:
#    - Product-level details, items, quantity, pricing

# 3. tbl_fact_order_new:
#    - Payment, financials, order status, refunds

# 4. tbl_riderregistration:
#    - Rider/driver details and profile
# """

# # ─── Prompt ────────────────────────────────────────────────────────────────────
# prompt = PromptTemplate(
#     template="""
# You are an intelligent intent classification system for a customer care chatbot.

# {intent_categories}

# {table_map}

# Instructions:
# 1. Carefully read the user query — handle all phrasings, typos, Hinglish, and informal language.
# 2. Identify the single best matching intent from the categories above.
# 3. Assign a confidence score between 0.0 (not sure) and 1.0 (very sure).
# 4. Select ALL relevant database tables needed to answer the query.
#    - If the query involves multiple aspects (e.g., order + payment), include multiple tables.
#    - Do NOT limit to just one table if more are relevant.
#    - Return a list of tables.w
# 5. Write a short reason explaining your choice.
# 6. Return ONLY valid JSON — no explanation, no markdown, no extra text.

# Output format (strictly follow this):
# {{
#   "intent": "<intent_label>",
#   "intent_category": "<ORDER | PAYMENT | PRODUCT | ACCOUNT | SUPPORT | GENERAL>",
#   "confidence": <float between 0.0 and 1.0>,
#   "tables": ["table1", "table2"],
#   "reason": "<one line explanation>"
# }}

# User Query: {query}
# """,
#     input_variables=["query", "intent_categories", "table_map"]
# )

# chain = prompt | llm | parser


# def classify_intent(user_query: str) -> dict:
#     """Classify intent of a customer query and return structured result."""
#     try:
#         result = chain.invoke({
#             "query": user_query,
#             "intent_categories": INTENT_CATEGORIES,
#             "table_map": TABLE_MAP
#         })
#         return result
#     except Exception as e:
#         return {
#             "intent": "unknown",
#             "intent_category": "GENERAL",
#             "confidence": 0.0,
#             "tables": [],
#             "reason": f"Classification failed: {str(e)}"
#         }


# def display_result(result: dict):
#     """Pretty-print the classification result."""
#     print("\n" + "="*50)
#     print("  INTENT CLASSIFICATION RESULT")
#     print("="*50)
#     print(f"  Intent          : {result.get('intent', 'N/A')}")
#     print(f"  Category        : {result.get('intent_category', 'N/A')}")
#     print(f"  Confidence      : {result.get('confidence', 0.0):.0%}")
#     print(f"  DB Tables       : {', '.join(result.get('tables', []))}")
#     print(f"  Reason          : {result.get('reason', 'N/A')}")
#     print("="*50 + "\n")


# # ─── Main loop ────────────────────────────────────────────────────────────────
# if __name__ == "__main__":
#     print("\n Customer Care Intent Classifier")
#     print(" Type your query below (or 'exit' to quit)\n")

#     while True:
#         user_query = input("You: ").strip()

#         if not user_query:
#             print("  Please enter a query.\n")
#             continue

#         if user_query.lower() in ("exit", "quit", "bye"):
#             print("Exiting. Goodbye!")
#             break

#         print("\n Classifying...")
#         result = classify_intent(user_query)
#         display_result(result)


























from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_ollama import OllamaLLM
import pandas as pd
import json
import re

# ---------------- LLM SETUP ----------------
llm = OllamaLLM(
    model="phi3:mini",
    temperature=0,
    num_predict=150,
    num_ctx=2048,
    streaming=False,
)

parser = JsonOutputParser()

# ---------------- INTENT DATA ----------------
INTENT_CATEGORIES = """
ORDER INTENTS:....
"""

TABLE_MAP = """
Tables:
1. kfh_orders:
   - Order tracking, delivery status, logistics, rider assignment

2. tbl_customerorderdetails:
   - Product-level details, items, quantity, pricing

3. tbl_fact_order_new:
   - Payment, financials, order status, refunds

4. tbl_riderregistration:
   - Rider/driver details and profile
"""

# ---------------- INTENT PROMPT ----------------
prompt = PromptTemplate(
    template="""
You are an intelligent intent classification system.

{intent_categories}
{table_map}

Return JSON:
{{
  "intent": "...",
  "intent_category": "...",
  "confidence": 0.0,
  "tables": ["..."],
  "reason": "..."
}}

User Query: {query}
""",
    input_variables=["query", "intent_categories", "table_map"]
)

chain = prompt | llm | parser

# ---------------- SQL GENERATION ----------------
sql_prompt = PromptTemplate(
    template="""
You are a SQL generator.

Tables:
- kfh_orders(Order ID, Delivery Status, Delivery Date, Rider, Eta)
- tbl_fact_order_new(Orderid, Deliverystatus, Paymentstatus, Refundstatus)
- tbl_customerorderdetails(Order ID, Product ID, Quantity, Totalamount)

Rules:
- Only SELECT queries
- Use correct column names EXACTLY
- No explanation

User Query: {query}
""",
    input_variables=["query"]
)

sql_chain = sql_prompt | llm

# ---------------- LOAD EXCEL ----------------
def load_excel():
    return {
        "kfh_orders": pd.read_excel(r"C:\Users\Mit.Gandhi\Desktop\chatbot\kfh_orders.xlsx"),
        "tbl_customerorderdetails": pd.read_excel(r"C:\Users\Mit.Gandhi\Desktop\chatbot\tbl_customerorderdetails.xlsx"),
        "tbl_fact_order_new": pd.read_excel(r"C:\Users\Mit.Gandhi\Desktop\chatbot\Tbl_fact_order_new.xlsx"),
    }

# ---------------- INTENT ----------------
def classify_intent(user_query):
    try:
        return chain.invoke({
            "query": user_query,
            "intent_categories": INTENT_CATEGORIES,
            "table_map": TABLE_MAP
        })
    except:
        return {"intent": "unknown", "tables": []}

# ---------------- ORDER ID EXTRACTION ----------------
def extract_order_id(query):
    match = re.search(r'\d+', query)
    return int(match.group()) if match else None

# ---------------- SQL EXECUTION ----------------
def execute_query(sql_query, tables, order_id=None):
    try:
        print("\n[SQL]:", sql_query)

        sql_query = sql_query.lower()

        # Detect table
        if "kfh_orders" in sql_query:
            df = tables["kfh_orders"]
            col = "Order ID"

        elif "tbl_fact_order_new" in sql_query:
            df = tables["tbl_fact_order_new"]
            col = "Orderid"

        elif "tbl_customerorderdetails" in sql_query:
            df = tables["tbl_customerorderdetails"]
            col = "Order ID"

        else:
            return "No valid table found"

        # Apply WHERE condition
        if order_id:
            df = df[df[col] == order_id]

        return df.head(5).to_dict(orient="records")

    except Exception as e:
        return f"Execution failed: {str(e)}"

# ---------------- DISPLAY ----------------
def display_result(result):
    print("\n" + "="*50)
    print("INTENT RESULT")
    print("="*50)
    print("Intent:", result.get("intent"))
    print("Tables:", result.get("tables"))
    print("="*50)

# ---------------- MAIN ----------------
if __name__ == "__main__":
    print("\n Chatbot with Excel DB")
    print("Type 'exit' to quit\n")

    tables = load_excel()

    while True:
        query = input("You: ").strip()

        if query.lower() == "exit":
            break

        # 1. Intent
        result = classify_intent(query)
        display_result(result)

        # 2. Extract order id
        order_id = extract_order_id(query)

        # 3. Generate SQL
        sql_query = sql_chain.invoke({"query": query}).strip()

        # 4. Execute
        data = execute_query(sql_query, tables, order_id)

        print("\n DATA:")
        print(json.dumps(data, indent=2))