import random
import os
import sqlite3
import pandas as pd
from flask import Flask, request, render_template, jsonify
import datetime
from math import radians, sin, cos, sqrt, atan2

app = Flask(__name__)

# SQLite ローカルパス
LOCAL_DB_PATH = "ramenstore.db"

# likes テーブル初期化
def ensure_likes_table():
    with sqlite3.connect(LOCAL_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                店名 TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        """)

ensure_likes_table()

general_questions = [
    "体疲れてるん？", "頭疲れてるん？", "今ストレスたまってるん？",
    "自分の人生生きてるか？", "腹はめちゃこ減ってるん？",
    "今日は運がよかったか？", "今日は楽しい出来事があったんか？"
]

fixed_questions = [
    "こってり派？あっさり派？",
    "太麺派？細麺派？",
    "硬麺派？柔らか麺派？"
]

weekday_questions = {
    0: "今週の始まりやけど元気はあるか？",
    1: "スープまで飲み干したい気分か？",
    2: "週末の予定は立てたんか？",
    3: "今の自分は頑張ってるって言い張れるか？",
    4: "今週は災難やったか？",
    5: "今週頑張った自分にご褒美をあげたいと思てるやろー？",
    6: "明日からまたがんばろな！"
}

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c * 1000

def get_likes_dict():
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 店名, count FROM likes")
    likes_data = dict(cursor.fetchall())
    conn.close()
    return likes_data

def load_ramen_shops_from_db(ramen_type):
    try:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 店名, 修正後住所 AS 住所, 緯度, 経度, ラーメンの種類, 詳細リンク, 写真1, 写真2, 写真3
            FROM ramen_stores
            WHERE ラーメンの種類 = ?
        """, (ramen_type,))
        rows = cursor.fetchall()
        conn.close()
        return pd.DataFrame([dict(row) for row in rows])
    except Exception as e:
        return f"DBエラー: {e}"

@app.route("/", methods=["GET"])
def index():
    current_day = datetime.datetime.now().weekday()
    current_hour = datetime.datetime.now().hour
    day_question = weekday_questions.get(current_day, "今日は何か楽しいことがあったかー？")

    if current_hour < 12:
        time_question = ["今日の気分はいいんか？", "今日なんかに挑戦したい気分なんか？"]
    else:
        time_question = ["今日は頑張ったと思えるんか？", "今日は何かに挑戦したんか？"]

    random_questions = random.sample(general_questions, 3)
    questions = fixed_questions + [day_question] + time_question + random_questions
    return render_template("index.html", questions=questions)

@app.route("/result", methods=["POST"])
def result():
    total_questions = len(fixed_questions) + 5  # 固定3 + 曜日1 + 時間2 + ランダム3 → loop index合わせて調整
    answers = {f"q{i}": request.form.get(f"q{i}") for i in range(total_questions)}

    # 簡易ラーメンタイプ判定（例）
    if answers.get("q0") == "左":
        if answers.get("q1") == "左":
            ramen_type = "豚骨ラーメン"
        else:
            ramen_type = "塩ラーメン"
    elif answers.get("q1") == "右":
        ramen_type = "味噌ラーメン"
    else:
        ramen_type = "醤油ラーメン"
    lat = request.form.get("lat")
    lng = request.form.get("lng")
    if not lat or not lng:
        return "緯度経度が取得できませんでした。ブラウザで位置情報を許可してください。"

    try:
        user_lat = float(lat)
        user_lng = float(lng)
    except ValueError:
        return "緯度経度の形式が正しくありません。"

    df = load_ramen_shops_from_db(ramen_type)
    likes_dict = get_likes_dict()

    if not df.empty:
        df["距離"] = df.apply(lambda row: calculate_distance(user_lat, user_lng, row["緯度"], row["経度"]), axis=1)
        top_shops = df.sort_values(by="距離").head(3)
        top_shops["距離_表示"] = top_shops["距離"].apply(lambda d: f"{int(d)}m" if d < 1000 else f"{d/1000:.1f}km")
        top_shops["いいね"] = top_shops["店名"].apply(lambda name: likes_dict.get(name, 0))
        recommended_shops = top_shops.to_dict(orient="records")
    else:
        recommended_shops = []

    # 宅麺データ
    try:
        df_takumen = pd.read_csv("takumen_with_ramen_type.csv", encoding="shift_jis")
        recommended_takumen = df_takumen[df_takumen["ラーメンの種類"] == ramen_type].sample(n=min(3,len(df_takumen))).to_dict(orient="records")
    except:
        recommended_takumen = []

    return render_template("result.html", ramen_type=ramen_type, shops=recommended_shops, takumen_products=recommended_takumen, user_lat=user_lat, user_lng=user_lng)

@app.route("/like", methods=["POST"])
def like():
    shop_name = request.json.get("shop_name")
    if not shop_name:
        return jsonify({"error": "店名が指定されていません。"}), 400

    with sqlite3.connect(LOCAL_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO likes (店名, count) VALUES (?, 0)", (shop_name,))
        cursor.execute("UPDATE likes SET count = count + 1 WHERE 店名 = ?", (shop_name,))
        conn.commit()
        cursor.execute("SELECT count FROM likes WHERE 店名 = ?", (shop_name,))
        new_count = cursor.fetchone()[0]

    return jsonify({"message": "いいね完了", "count": new_count})

if __name__ == "__main__":
    app.run(debug=True, port=3000)
