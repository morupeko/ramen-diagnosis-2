import pandas as pd
import sqlite3

# CSV読み込み
df = pd.read_csv("ramen_store_info_with_3_photos.csv")

# 「店名」が重複している行を削除（最初の1件だけ残す）
df = df.drop_duplicates(subset="店名", keep="first")

# 不要なXMLっぽい文字列を削除（例: <results>～</results>）
df["修正後住所"] = df["修正後住所"].astype(str).str.replace(r"<.*?>", "", regex=True)

# SQLiteに保存
conn = sqlite3.connect("ramenstore.db")
df.to_sql("ramen_stores", conn, if_exists="replace", index=False)

# 店名にユニークインデックス作成
conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_ramen_name ON ramen_stores ("店名");')

conn.commit()
conn.close()

print("CSVからSQLiteへ変換完了しました！")
