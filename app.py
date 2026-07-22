from flask import Flask, render_template, request, redirect, url_for
import psycopg2
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

app = Flask(__name__)

# 🔌 DATABASE
def get_db():
    return psycopg2.connect(
        dbname="finance_db",
        user="postgres",
        password="password",
        host="localhost",
        port="5432"
    )

# 🧠 ALERT (EXPLAINABLE)
def generate_alert(total, avg):
    if avg == 0:
        return "No data yet"

    percent = ((total - avg) / avg) * 100
    percent = min(percent, 200)  # avoid huge %

    if percent > 30:
        return f"⚠️ You spent ₹{int(total)} — {round(percent,1)}% higher than your average (₹{int(avg)})"
    else:
        return "✅ Your spending is under control"

# 📈 PREDICTION
def predict_next_month():
    conn = get_db()

    df = pd.read_sql("""
        SELECT DATE_TRUNC('month', date) AS month, SUM(amount) AS total
        FROM expenses
        GROUP BY month
        ORDER BY month
    """, conn)

    conn.close()

    if len(df) < 2:
        return 0

    df = df.reset_index(drop=True)
    df['month_index'] = np.arange(len(df))

    X = df[['month_index']]
    y = df['total']

    model = LinearRegression()
    model.fit(X, y)

    prediction = model.predict([[len(df)]])[0]

    # limit unrealistic prediction
    last_total = df['total'].iloc[-1]
    prediction = min(prediction, last_total * 1.5)

    return round(prediction, 2)

# 🏠 HOME
@app.route('/')
def home():
    conn = get_db()
    cur = conn.cursor()

    # CATEGORY CHART (ALL DATA)
    cur.execute("""
        SELECT category, SUM(amount)
        FROM expenses
        GROUP BY category
    """)
    chart = cur.fetchall()

    # CURRENT MONTH TOTAL
    cur.execute("""
        SELECT SUM(amount)
        FROM expenses
        WHERE EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE)
        AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
    """)
    total = cur.fetchone()[0] or 0

    # AVG
    cur.execute("SELECT AVG(amount) FROM expenses")
    avg = cur.fetchone()[0] or 0

    # ✅ FIXED MONTHLY INSIGHT
    cur.execute("""
        SELECT category, SUM(amount) as total
        FROM expenses
        WHERE EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE)
        AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
        GROUP BY category
        ORDER BY total DESC
        LIMIT 1
    """)
    top_category = cur.fetchone()

    if not top_category:
        top_category = ("No data", 0)

    cur.close()
    conn.close()

    # ML
    alert = generate_alert(total, avg)
    prediction = predict_next_month()

    return render_template(
        "dashboard.html",
        chart=chart,
        total=total,
        avg=avg,
        alert=alert,
        prediction=prediction,
        top_category=top_category
    )

# ➕ ADD EXPENSE
@app.route('/add', methods=['POST'])
def add():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO expenses (date, category, amount, payment)
        VALUES (%s, %s, %s, %s)
    """, (
        request.form['date'],
        request.form['category'],
        request.form['amount'],
        request.form['payment']
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)