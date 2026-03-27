from flask import Flask, render_template, request, redirect, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename
from PIL import Image

import os, json, base64, math, io, uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = "vipheraid_expo_final_2026_madurai"

# Database config
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///viperaid.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)

# Animal classes allowed
ANIMAL_CLASSES = [
    "bird", "cat", "dog", "horse", "sheep",
    "cow", "elephant", "bear", "zebra", "giraffe"
]


# ───────────────── DATABASE MODELS ─────────────────
class Report(db.Model):
    id             = db.Column(db.String(40),  primary_key=True)
    created_at     = db.Column(db.DateTime,    default=datetime.utcnow)
    animal_type    = db.Column(db.String(50))
    breed          = db.Column(db.String(100))
    injury         = db.Column(db.String(200))
    severity       = db.Column(db.String(50))
    urgency        = db.Column(db.String(20),  default="Medium")
    location_text  = db.Column(db.String(200))
    geo            = db.Column(db.String(100))
    description    = db.Column(db.Text)
    reporter_name  = db.Column(db.String(100))
    reporter_phone = db.Column(db.String(20))
    status         = db.Column(db.String(20),  default="Reported")
    assigned_to    = db.Column(db.String(100))
    photo_url      = db.Column(db.String(300))
    latitude       = db.Column(db.Float)
    longitude      = db.Column(db.Float)
    is_emergency   = db.Column(db.Boolean,     default=False)


class Shelter(db.Model):
    id             = db.Column(db.Integer,     primary_key=True, autoincrement=True)
    created_at     = db.Column(db.DateTime,    default=datetime.utcnow)
    name           = db.Column(db.String(200), nullable=False)
    shelter_type   = db.Column(db.String(50))
    address        = db.Column(db.String(300))
    city           = db.Column(db.String(100))
    phone          = db.Column(db.String(30))
    email          = db.Column(db.String(100))
    geo            = db.Column(db.String(100))
    capacity       = db.Column(db.String(20))
    animals_helped = db.Column(db.String(200))
    description    = db.Column(db.Text)
    hours          = db.Column(db.String(100))
    website        = db.Column(db.String(200))


with app.app_context():
    db.create_all()


# ───────────────── PAGES ─────────────────
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

@app.route("/donate")
def donate():
    return render_template("donate.html")

@app.route("/shelter")
def shelter_page():
    return render_template("shelter.html")


# ───────────────── AUTH ─────────────────
@app.route("/rescue-login", methods=["GET", "POST"])
def rescue_login():
    if request.method == "POST":
        org  = request.form.get("org",  "").strip()
        code = request.form.get("code", "").strip()
        if code == "VIPERNGO":
            session["rescuer"] = True
            session["org"]     = org or "NGO"
            return redirect("/rescue")
        flash("Invalid NGO code. Try: VIPERNGO")
        return redirect("/rescue-login")
    return render_template("rescue-login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/api/ai-report", methods=["POST"])
def ai_report():
    try:
        photo = request.files.get("photo")
        if not photo:
            return jsonify({"success": False, "error": "No photo uploaded"}), 400

        filename = f"{uuid.uuid4().hex}.jpg"
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        photo.save(path)

        # YOLO detection — use as fallback if reporter didn't name the animal
        image = Image.open(path).convert("RGB")
        results = model(image)

        detected_animal = "Unknown"
        for r in results:
            for box in r.boxes:
                cls = int(box.cls[0])
                detected_animal = model.names.get(cls, "Unknown")
                break

        # Reporter-supplied fields (from the new form)
        animal_name    = request.form.get("animal_name", "").strip()
        description    = request.form.get("description", "").strip()
        reporter_name  = request.form.get("reporter_name", "").strip()
        reporter_phone = request.form.get("reporter_phone", "").strip()

        # Use reporter-supplied name if given, else fall back to YOLO
        final_animal = animal_name if animal_name else detected_animal

        # GPS from frontend
        latitude  = request.form.get("latitude", type=float)
        longitude = request.form.get("longitude", type=float)
        geo       = f"{latitude},{longitude}" if latitude and longitude else None

        report_id = "VA" + uuid.uuid4().hex[:10].upper()

        new_report = Report(
            id=report_id,
            animal_type=final_animal,
            breed="Unknown",
            injury="Not analyzed",
            severity="Medium",
            urgency="Medium",
            description=description or "Animal reported via image upload. Needs inspection.",
            photo_url=f"/static/uploads/{filename}",
            latitude=latitude,
            longitude=longitude,
            geo=geo,
            reporter_name=reporter_name or None,
            reporter_phone=reporter_phone or None,
            status="Reported"
        )

        db.session.add(new_report)
        db.session.commit()

        return jsonify({
            "success":       True,
            "id":            new_report.id,
            "animal":        new_report.animal_type,
            "photoUrl":      new_report.photo_url,
            "reporterName":  new_report.reporter_name,
            "reporterPhone": new_report.reporter_phone,
            "description":   new_report.description,
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ───────────────── REPORTS LIST (for rescue dashboard) ─────────────────
@app.route("/api/reports")
def api_get_reports():
    reports = Report.query.order_by(Report.created_at.desc()).all()
    result = []
    for r in reports:
        result.append({
            "id":            r.id,
            "createdAt":     r.created_at.isoformat() if r.created_at else None,
            "animalType":    r.animal_type,
            "description":   r.description,
            "photoUrl":      r.photo_url,
            "geo":           r.geo,
            "locationText":  r.location_text,
            "urgency":       r.urgency or "Medium",
            "severity":      r.severity,
            "status":        r.status or "Reported",
            "assignedTo":    r.assigned_to,
            "reporterName":  r.reporter_name,
            "reporterPhone": r.reporter_phone,
            "isEmergency":   bool(r.is_emergency),
        })
    return jsonify(result)


@app.route("/api/report/<string:report_id>", methods=["POST"])
def api_update_report(report_id):
    report = Report.query.get_or_404(report_id)
    data = request.json or {}
    if "status" in data:
        report.status = data["status"]
    if "assignedTo" in data:
        report.assigned_to = data["assignedTo"]
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/report/<string:report_id>", methods=["DELETE"])
def api_delete_report(report_id):
    report = Report.query.get_or_404(report_id)
    db.session.delete(report)
    db.session.commit()
    return jsonify({"success": True})

# ───────────────── NEARBY SHELTERS (NO GEO) ─────────────────
@app.route("/api/nearby-shelters")
def api_nearby_shelters():
    try:
        shelters = Shelter.query.order_by(Shelter.created_at.desc()).all()

        result = []
        for i, s in enumerate(shelters):
            result.append({
                "id": s.id,
                "name": s.name,
                "shelter_type": s.shelter_type,
                "address": s.address,
                "city": s.city,
                "phone": s.phone,
                "email": s.email,
                "hours": s.hours,
                "animals_helped": s.animals_helped,
                
                # fake distance just for UI
                "distance_km": round(1 + i * 2, 1)
            })

        return jsonify({"shelters": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
# ───────────────── SHELTER APIs ─────────────────
@app.route("/api/shelter", methods=["POST"])
def api_create_shelter():
    data = request.json or {}
    s = Shelter(
        name           = data.get("name"),
        shelter_type   = data.get("shelter_type"),
        address        = data.get("address"),
        city           = data.get("city"),
        phone          = data.get("phone"),
        email          = data.get("email"),
        geo            = data.get("geo"),
        capacity       = data.get("capacity"),
        animals_helped = data.get("animals_helped"),
        description    = data.get("description"),
        hours          = data.get("hours"),
        website        = data.get("website")
    )
    db.session.add(s)
    db.session.commit()
    return jsonify({"success": True, "id": s.id})


@app.route("/api/shelters")
def api_get_shelters():
    shelters = Shelter.query.order_by(Shelter.created_at.desc()).all()
    return jsonify([{
        "id":             s.id,
        "name":           s.name,
        "shelter_type":   s.shelter_type,
        "address":        s.address,
        "city":           s.city,
        "phone":          s.phone,
        "email":          s.email,
        "geo":            s.geo,
        "capacity":       s.capacity,
        "animals_helped": s.animals_helped,
        "description":    s.description,
        "hours":          s.hours,
        "website":        s.website
    } for s in shelters])


@app.route("/api/shelter/<int:shelter_id>", methods=["PUT"])
def api_update_shelter(shelter_id):
    shelter = Shelter.query.get_or_404(shelter_id)
    data    = request.json or {}
    shelter.name           = data.get("name",           shelter.name)
    shelter.shelter_type   = data.get("shelter_type",   shelter.shelter_type)
    shelter.address        = data.get("address",        shelter.address)
    shelter.city           = data.get("city",           shelter.city)
    shelter.phone          = data.get("phone",          shelter.phone)
    shelter.email          = data.get("email",          shelter.email)
    shelter.geo            = data.get("geo",            shelter.geo)
    shelter.capacity       = data.get("capacity",       shelter.capacity)
    shelter.animals_helped = data.get("animals_helped", shelter.animals_helped)
    shelter.description    = data.get("description",    shelter.description)
    shelter.hours          = data.get("hours",          shelter.hours)
    shelter.website        = data.get("website",        shelter.website)
    db.session.commit()
    return jsonify({"success": True, "id": shelter.id})


@app.route("/api/shelter/<int:shelter_id>", methods=["DELETE"])
def api_delete_shelter(shelter_id):
    shelter = Shelter.query.get_or_404(shelter_id)
    db.session.delete(shelter)
    db.session.commit()
    return jsonify({"success": True})


# ───────────────── AI ANIMAL DETECTION ─────────────────
@app.route("/api/detect-animal", methods=["POST"])
def api_detect_animal():
    data      = request.json or {}
    image_b64 = data.get("image", "")

    if not image_b64:
        return jsonify({"isAnimal": False})

    try:
        image_bytes = base64.b64decode(image_b64)
        image       = Image.open(io.BytesIO(image_bytes))
        results     = model(image)

        for r in results:
            for box in r.boxes:
                cls   = int(box.cls[0])
                label = model.names[cls]

                if label in ANIMAL_CLASSES:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    bbox = {
                        "x":      x1 / image.width,
                        "y":      y1 / image.height,
                        "width":  (x2 - x1) / image.width,
                        "height": (y2 - y1) / image.height
                    }
                    return jsonify({
                        "isAnimal":   True,
                        "animalType": label,
                        "bbox":       bbox
                    })

        return jsonify({"isAnimal": False, "detectedAs": "No animal detected"})

    except Exception as e:
        return jsonify({"isAnimal": False, "detectedAs": "AI error"})


# ───────────────── MISC ─────────────────
@app.route("/favicon.ico")
def favicon():
    return "", 204


@app.route("/api/public-stats")
def api_public_stats():
    total    = Report.query.count()
    resolved = Report.query.filter_by(status="Completed").count()
    active   = Report.query.filter(Report.status != "Completed").count()
    return jsonify({"total": total, "resolved": resolved, "active": active})


if __name__ == "__main__":
    app.run(host="0.0.0.0",
    port=int(os.environ.get("PORT",5000)))
