import sqlite3
conn = sqlite3.connect("ramenstore.db")
cur = conn.cursor()
cur.execute("SELECT 店名, ラーメンの種類 FROM ramen_stores LIMIT 5;")
print(cur.fetchall())
conn.close()