from flask import Flask, render_template, request, redirect, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os, uuid
from dotenv import load_dotenv

# Load env
load_dotenv()

app = Flask(__name__)
app.secret_key = "vipheraid_expo_final_2026_madurai"

# Config
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///viperaid.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ───────── DATABASE MODELS ─────────
class Report(db.Model):
    id = db.Column(db.String(40), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    animal_type = db.Column(db.String(50))
    description = db.Column(db.Text)
    reporter_name = db.Column(db.String(100))
    reporter_phone = db.Column(db.String(20))
    status = db.Column(db.String(20), default="Reported")


class Shelter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    address = db.Column(db.String(300))
    city = db.Column(db.String(100))
    phone = db.Column(db.String(30))


with app.app_context():
    db.create_all()

# ───────── PAGES ─────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/report")
def report():
    return render_template("report.html")

@app.route("/emergency")
def emergency():
    return render_template("emergency.html")

@app.route("/rescue")
def rescue():
    if not session.get("rescuer"):
        return redirect("/rescue-login")
    return render_template("rescue.html")

# ───────── AUTH ─────────
@app.route("/rescue-login", methods=["GET", "POST"])
def rescue_login():
    if request.method == "POST":
        code = request.form.get("code")
        if code == "VIPERNGO":
            session["rescuer"] = True
            return redirect("/rescue")
        flash("Invalid code")
    return render_template("rescue-login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ───────── REPORT API ─────────
@app.route("/api/report", methods=["POST"])
def create_report():
    data = request.json

    report = Report(
        id="VA" + uuid.uuid4().hex[:10].upper(),
        animal_type=data.get("animal"),
        description=data.get("description"),
        reporter_name=data.get("name"),
        reporter_phone=data.get("phone"),
    )

    db.session.add(report)
    db.session.commit()

    return jsonify({"success": True, "id": report.id})

@app.route("/api/reports")
def get_reports():
    reports = Report.query.all()
    return jsonify([{
        "id": r.id,
        "animal": r.animal_type,
        "description": r.description,
        "status": r.status
    } for r in reports])

# ───────── SHELTERS ─────────
@app.route("/api/shelters")
def get_shelters():
    shelters = Shelter.query.all()
    return jsonify([{
        "id": s.id,
        "name": s.name,
        "city": s.city,
        "phone": s.phone
    } for s in shelters])

@app.route("/api/shelter", methods=["POST"])
def add_shelter():
    data = request.json

    s = Shelter(
        name=data.get("name"),
        address=data.get("address"),
        city=data.get("city"),
        phone=data.get("phone")
    )

    db.session.add(s)
    db.session.commit()

    return jsonify({"success": True})

# ───────── STATS ─────────
@app.route("/api/stats")
def stats():
    total = Report.query.count()
    return jsonify({"total": total})

# ───────── RUN ─────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)