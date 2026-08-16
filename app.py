from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "alnaseem-change-this-secret"
DB = os.path.join(os.path.dirname(__file__), "alnaseem.db")

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.execute("""CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        passport TEXT,
        phone TEXT,
        notes TEXT,
        created_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        service TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'قيد الإجراء',
        application_no TEXT,
        issue_date TEXT,
        entry_date TEXT,
        exit_date TEXT,
        total REAL DEFAULT 0,
        paid REAL DEFAULT 0,
        expenses REAL DEFAULT 0,
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(client_id) REFERENCES clients(id)
    )""")
    conn.commit()
    conn.close()
init_db()

@app.route("/")
def dashboard():
    conn = db()
    stats = {
        "clients": conn.execute("SELECT COUNT(*) c FROM clients").fetchone()["c"],
        "transactions": conn.execute("SELECT COUNT(*) c FROM transactions").fetchone()["c"],
        "pending": conn.execute("SELECT COUNT(*) c FROM transactions WHERE status='قيد الإجراء'").fetchone()["c"],
        "balance": conn.execute("SELECT COALESCE(SUM(total-paid),0) x FROM transactions").fetchone()["x"],
    }
    recent = conn.execute("""SELECT t.*, c.name client_name FROM transactions t
                             JOIN clients c ON c.id=t.client_id
                             ORDER BY t.id DESC LIMIT 10""").fetchall()
    conn.close()
    return render_template("dashboard.html", stats=stats, recent=recent)

@app.route("/clients")
def clients():
    q = request.args.get("q","").strip()
    conn = db()
    if q:
        rows = conn.execute("""SELECT * FROM clients WHERE name LIKE ? OR passport LIKE ? OR phone LIKE ?
                               ORDER BY id DESC""", (f"%{q}%",f"%{q}%",f"%{q}%")).fetchall()
    else:
        rows = conn.execute("SELECT * FROM clients ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("clients.html", clients=rows, q=q)

@app.route("/clients/add", methods=["GET","POST"])
def add_client():
    if request.method == "POST":
        name = request.form["name"].strip()
        if not name:
            flash("الاسم مطلوب")
            return redirect(url_for("add_client"))
        conn=db()
        conn.execute("INSERT INTO clients(name,passport,phone,notes,created_at) VALUES(?,?,?,?,?)",
                     (name,request.form.get("passport"),request.form.get("phone"),
                      request.form.get("notes"),datetime.now().isoformat(timespec="seconds")))
        conn.commit(); conn.close()
        flash("تمت إضافة العميل بنجاح")
        return redirect(url_for("clients"))
    return render_template("client_form.html")

@app.route("/transactions")
def transactions():
    conn=db()
    rows=conn.execute("""SELECT t.*, c.name client_name FROM transactions t
                         JOIN clients c ON c.id=t.client_id ORDER BY t.id DESC""").fetchall()
    conn.close()
    return render_template("transactions.html", transactions=rows)

@app.route("/transactions/add", methods=["GET","POST"])
def add_transaction():
    conn=db()
    clients=conn.execute("SELECT id,name,passport FROM clients ORDER BY name").fetchall()
    if request.method=="POST":
        conn.execute("""INSERT INTO transactions
        (client_id,service,status,application_no,issue_date,entry_date,exit_date,total,paid,expenses,notes,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
            request.form["client_id"], request.form["service"], request.form["status"],
            request.form.get("application_no"), request.form.get("issue_date"),
            request.form.get("entry_date"), request.form.get("exit_date"),
            float(request.form.get("total") or 0), float(request.form.get("paid") or 0),
            float(request.form.get("expenses") or 0), request.form.get("notes"),
            datetime.now().isoformat(timespec="seconds")
        ))
        conn.commit(); conn.close()
        flash("تمت إضافة المعاملة")
        return redirect(url_for("transactions"))
    conn.close()
    return render_template("transaction_form.html", clients=clients)

@app.route("/reports")
def reports():
    conn=db()
    rows=conn.execute("""SELECT service, COUNT(*) count,
                         COALESCE(SUM(total),0) total,
                         COALESCE(SUM(paid),0) paid,
                         COALESCE(SUM(expenses),0) expenses,
                         COALESCE(SUM(total-paid-expenses),0) profit
                         FROM transactions GROUP BY service ORDER BY count DESC""").fetchall()
    conn.close()
    return render_template("reports.html", rows=rows)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
