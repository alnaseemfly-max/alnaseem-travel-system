from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "alnaseem-dev-secret-change-me")
DB = os.path.join(os.path.dirname(__file__), "alnaseem.db")

BUS_COMPANIES = ["درة المدينة", "الأفضل", "المتصدر", "النجار"]
STATUSES = ["قيد الإجراء", "تمت", "مرفوضة", "ملغاة"]

# --- إعداد نظام تسجيل الدخول (Flask-Login) ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "يرجى تسجيل الدخول أولاً للوصول لهذه الصفحة."

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

@login_manager.user_loader
def load_user(user_id):
    conn = db()
    u = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if u:
        return User(u["id"], u["username"], u["password_hash"])
    return None

# --- إعدادات قاعدة البيانات ---
def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    # جدول المستخدمين لتسجيل الدخول
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    )""")
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
    conn.execute("""CREATE TABLE IF NOT EXISTS bus_bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        company TEXT NOT NULL,
        booking_no TEXT,
        from_city TEXT,
        to_city TEXT,
        travel_date TEXT,
        seats INTEGER DEFAULT 1,
        total REAL DEFAULT 0,
        paid REAL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'قيد الإجراء',
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(client_id) REFERENCES clients(id)
    )""")
    conn.commit()
    conn.close()

@app.context_processor
def globals():
    return {"bus_companies": BUS_COMPANIES, "statuses": STATUSES}

# --- مسارات المصادقة (Auth Routes) ---

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
        
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        conn = db()
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user["password_hash"], password):
            user_obj = User(user["id"], user["username"], user["password_hash"])
            login_user(user_obj)
            return redirect(url_for("dashboard"))
        else:
            flash("اسم المستخدم أو كلمة المرور غير صحيحة")
            
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("تم تسجيل الخروج بنجاح")
    return redirect(url_for("login"))

# مسار لمرة واحدة لإنشاء حساب المدير الأول
@app.route("/create-admin-init")
def create_admin_init():
    conn = db()
    hashed_password = generate_password_hash("admin123", method="scrypt")
    try:
        conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", ("admin", hashed_password))
        conn.commit()
        msg = "تم إنشاء الحساب الرئيسي بنجاح! اسم المستخدم: admin | كلمة المرور: admin123"
    except Exception:
        msg = "حساب المدير موجود بالفعل."
    finally:
        conn.close()
    return msg

# --- المسارات المحمية (Protected Routes) ---

@app.route("/")
@login_required
def dashboard():
    conn = db()
    stats = {
        "clients": conn.execute("SELECT COUNT(*) c FROM clients").fetchone()["c"],
        "transactions": conn.execute("SELECT COUNT(*) c FROM transactions").fetchone()["c"],
        "bus_bookings": conn.execute("SELECT COUNT(*) c FROM bus_bookings").fetchone()["c"],
        "pending": conn.execute("""SELECT COUNT(*) c FROM transactions
                                   WHERE status='قيد الإجراء'""").fetchone()["c"],
        "balance": conn.execute("""SELECT COALESCE(SUM(total-paid),0) x
                                   FROM transactions""").fetchone()["x"],
    }
    recent = conn.execute("""SELECT t.*, c.name client_name FROM transactions t
                             JOIN clients c ON c.id=t.client_id
                             ORDER BY t.id DESC LIMIT 8""").fetchall()
    conn.close()
    return render_template("dashboard.html", stats=stats, recent=recent)

@app.route("/clients")
@login_required
def clients():
    q = request.args.get("q","").strip()
    conn = db()
    if q:
        rows = conn.execute("""SELECT * FROM clients
            WHERE name LIKE ? OR passport LIKE ? OR phone LIKE ?
            ORDER BY id DESC""", (f"%{q}%",f"%{q}%",f"%{q}%")).fetchall()
    else:
        rows = conn.execute("SELECT * FROM clients ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("clients.html", clients=rows, q=q)

@app.route("/clients/add", methods=["GET","POST"])
@login_required
def add_client():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        if not name:
            flash("الاسم مطلوب")
            return redirect(url_for("add_client"))
        conn=db()
        conn.execute("""INSERT INTO clients(name,passport,phone,notes,created_at)
                        VALUES(?,?,?,?,?)""",
                     (name,request.form.get("passport"),request.form.get("phone"),
                      request.form.get("notes"),
                      datetime.now().isoformat(timespec="seconds")))
        conn.commit(); conn.close()
        flash("تمت إضافة العميل بنجاح")
        return redirect(url_for("clients"))
    return render_template("client_form.html", client=None)

@app.route("/clients/<int:client_id>/edit", methods=["GET","POST"])
@login_required
def edit_client(client_id):
    conn=db()
    client=conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if not client:
        conn.close(); flash("العميل غير موجود"); return redirect(url_for("clients"))
    if request.method=="POST":
        name=request.form.get("name","").strip()
        if not name:
            flash("الاسم مطلوب"); conn.close()
            return redirect(url_for("edit_client", client_id=client_id))
        conn.execute("""UPDATE clients SET name=?, passport=?, phone=?, notes=?
                        WHERE id=?""",
                     (name,request.form.get("passport"),request.form.get("phone"),
                      request.form.get("notes"),client_id))
        conn.commit(); conn.close()
        flash("تم تعديل بيانات العميل")
        return redirect(url_for("clients"))
    conn.close()
    return render_template("client_form.html", client=client)

@app.post("/clients/<int:client_id>/delete")
@login_required
def delete_client(client_id):
    conn=db()
    count=conn.execute("SELECT COUNT(*) c FROM transactions WHERE client_id=?", (client_id,)).fetchone()["c"]
    count += conn.execute("SELECT COUNT(*) c FROM bus_bookings WHERE client_id=?", (client_id,)).fetchone()["c"]
    if count:
        flash("لا يمكن حذف العميل لأنه مرتبط بمعاملات أو حجوزات")
    else:
        conn.execute("DELETE FROM clients WHERE id=?", (client_id,))
        conn.commit(); flash("تم حذف العميل")
    conn.close()
    return redirect(url_for("clients"))

@app.route("/transactions")
@login_required
def transactions():
    conn=db()
    rows=conn.execute("""SELECT t.*, c.name client_name FROM transactions t
                         JOIN clients c ON c.id=t.client_id ORDER BY t.id DESC""").fetchall()
    conn.close()
    return render_template("transactions.html", transactions=rows)

@app.route("/transactions/add", methods=["GET","POST"])
@login_required
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
            datetime.now().isoformat(timespec="seconds")))
        conn.commit(); conn.close()
        flash("تمت إضافة المعاملة")
        return redirect(url_for("transactions"))
    conn.close()
    return render_template("transaction_form.html", clients=clients, transaction=None)

@app.route("/transactions/<int:transaction_id>/edit", methods=["GET","POST"])
@login_required
def edit_transaction(transaction_id):
    conn=db()
    t=conn.execute("SELECT * FROM transactions WHERE id=?", (transaction_id,)).fetchone()
    clients=conn.execute("SELECT id,name,passport FROM clients ORDER BY name").fetchall()
    if not t:
        conn.close(); flash("المعاملة غير موجودة"); return redirect(url_for("transactions"))
    if request.method=="POST":
        conn.execute("""UPDATE transactions SET client_id=?, service=?, status=?,
            application_no=?, issue_date=?, entry_date=?, exit_date=?, total=?, paid=?,
            expenses=?, notes=? WHERE id=?""", (
            request.form["client_id"], request.form["service"], request.form["status"],
            request.form.get("application_no"), request.form.get("issue_date"),
            request.form.get("entry_date"), request.form.get("exit_date"),
            float(request.form.get("total") or 0), float(request.form.get("paid") or 0),
            float(request.form.get("expenses") or 0), request.form.get("notes"),
            transaction_id))
        conn.commit(); conn.close()
        flash("تم تعديل المعاملة")
        return redirect(url_for("transactions"))
    conn.close()
    return render_template("transaction_form.html", clients=clients, transaction=t)

@app.post("/transactions/<int:transaction_id>/delete")
@login_required
def delete_transaction(transaction_id):
    conn=db(); conn.execute("DELETE FROM transactions WHERE id=?", (transaction_id,))
    conn.commit(); conn.close(); flash("تم حذف المعاملة")
    return redirect(url_for("transactions"))

@app.route("/bus-bookings")
@login_required
def bus_bookings():
    conn=db()
    rows=conn.execute("""SELECT b.*, c.name client_name, c.passport
                         FROM bus_bookings b JOIN clients c ON c.id=b.client_id
                         ORDER BY b.id DESC""").fetchall()
    conn.close()
    return render_template("bus_bookings.html", bookings=rows)

@app.route("/bus-bookings/add", methods=["GET","POST"])
@login_required
def add_bus_booking():
    conn=db()
    clients=conn.execute("SELECT id,name,passport FROM clients ORDER BY name").fetchall()
    if request.method=="POST":
        conn.execute("""INSERT INTO bus_bookings
            (client_id,company,booking_no,from_city,to_city,travel_date,seats,total,paid,status,notes,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (
            request.form["client_id"], request.form["company"], request.form.get("booking_no"),
            request.form.get("from_city"), request.form.get("to_city"),
            request.form.get("travel_date"), int(request.form.get("seats") or 1),
            float(request.form.get("total") or 0), float(request.form.get("paid") or 0),
            request.form["status"], request.form.get("notes"),
            datetime.now().isoformat(timespec="seconds")))
        conn.commit(); conn.close()
        flash("تمت إضافة حجز الباص")
        return redirect(url_for("bus_bookings"))
    conn.close()
    return render_template("bus_booking_form.html", clients=clients, booking=None)

@app.route("/bus-bookings/<int:booking_id>/edit", methods=["GET","POST"])
@login_required
def edit_bus_booking(booking_id):
    conn=db()
    b=conn.execute("SELECT * FROM bus_bookings WHERE id=?", (booking_id,)).fetchone()
    clients=conn.execute("SELECT id,name,passport FROM clients ORDER BY name").fetchall()
    if not b:
        conn.close(); flash("الحجز غير موجود"); return redirect(url_for("bus_bookings"))
    if request.method=="POST":
        conn.execute("""UPDATE bus_bookings SET client_id=?, company=?, booking_no=?,
            from_city=?, to_city=?, travel_date=?, seats=?, total=?, paid=?, status=?, notes=?
            WHERE id=?""", (
            request.form["client_id"], request.form["company"], request.form.get("booking_no"),
            request.form.get("from_city"), request.form.get("to_city"),
            request.form.get("travel_date"), int(request.form.get("seats") or 1),
            float(request.form.get("total") or 0), float(request.form.get("paid") or 0),
            request.form["status"], request.form.get("notes"), booking_id))
        conn.commit(); conn.close(); flash("تم تعديل حجز الباص")
        return redirect(url_for("bus_bookings"))
    conn.close()
    return render_template("bus_booking_form.html", clients=clients, booking=b)

@app.post("/bus-bookings/<int:booking_id>/delete")
@login_required
def delete_bus_booking(booking_id):
    conn=db(); conn.execute("DELETE FROM bus_bookings WHERE id=?", (booking_id,))
    conn.commit(); conn.close(); flash("تم حذف الحجز")
    return redirect(url_for("bus_bookings"))

@app.route("/reports")
@login_required
def reports():
    conn=db()
    rows=conn.execute("""SELECT service, COUNT(*) count,
                         COALESCE(SUM(total),0) total,
                         COALESCE(SUM(paid),0) paid,
                         COALESCE(SUM(expenses),0) expenses,
                         COALESCE(SUM(total-paid-expenses),0) profit
                         FROM transactions GROUP BY service ORDER BY count DESC""").fetchall()
    bus=conn.execute("""SELECT company, COUNT(*) count,
                        COALESCE(SUM(total),0) total,
                        COALESCE(SUM(paid),0) paid
                        FROM bus_bookings GROUP BY company ORDER BY count DESC""").fetchall()
    conn.close()
    return render_template("reports.html", rows=rows, bus=bus)

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
