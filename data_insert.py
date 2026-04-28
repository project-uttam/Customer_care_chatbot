import pandas as pd
from sqlalchemy import create_engine

# Load Excel
df = pd.read_excel(r"C:\Users\Aryan.Gaddadavara\Desktop\chatbot\excel_files\Tbl_fact_order_new (1).xlsx")

# Clean columns
df.columns = df.columns.str.strip().str.replace(" ", "_").str.lower()

# Connect to PostgreSQL
engine = create_engine("postgresql://postgres:Your_Password@localhost:5432/chatbot_db")

# Insert data (auto-create table)
df.to_sql("Fact_name", engine, if_exists="replace", index=False)

print("✅ Data inserted successfully!")




# import pandas as pd
# from sqlalchemy import create_engine

# # ----------------------------
# # Display Settings (IMPORTANT)
# # ----------------------------
# pd.set_option('display.max_columns', None)     # show all columns
# pd.set_option('display.width', None)           # no line wrapping
# pd.set_option('display.max_colwidth', None)    # show full column content

# # ----------------------------
# # Connect to PostgreSQL
# # ----------------------------
# engine = create_engine("postgresql://postgres:Kisan%40123@127.0.0.1:5432/chatbot_db")

# # ----------------------------
# # Check current database
# # ----------------------------
# db = pd.read_sql("SELECT current_database();", engine)
# print("\n✅ Current Database:\n", db.to_string(index=False))

# # ----------------------------
# # Check available tables
# # ----------------------------
# tables = pd.read_sql("""
# SELECT table_name 
# FROM information_schema.tables 
# WHERE table_schema = 'public';
# """, engine)

# print("\n📊 Tables in Database:\n", tables.to_string(index=False))

# # ----------------------------
# # Fetch data from orders table
# # ----------------------------
# df = pd.read_sql("SELECT * FROM orders LIMIT 5;", engine)

# print("\n📦 Orders Data:\n")
# print(df.to_string(index=False))

# # ----------------------------
# # Print column names separately (best for debugging)
# # ----------------------------
# print("\n🧾 Column Names:\n", list(df.columns))


