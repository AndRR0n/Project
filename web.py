from flask import Flask, render_template, request, jsonify
import threading
import time
import webbrowser

from database import init_db, get_all_points, upsert_point, delete_point

app = Flask(__name__)

# Инициализация базы при старте
init_db()


@app.route("/")
def index():
    points = get_all_points()
    return render_template("index.html", points=points)


@app.route("/update", methods=["POST"])
def update_field():
    data = request.json
    point_id = int(data["id"])
    field = data["field"]
    value = data["value"].strip()

    allowed_fields = ["name", "address", "phone", "status", "comment"]
    if field not in allowed_fields:
        return jsonify({"status": "error", "message": "Недопустимое поле"}), 400

    # Загружаем текущую запись
    points = get_all_points()
    point = next((p for p in points if p["id"] == point_id), None)
    if not point:
        return jsonify({"status": "error", "message": "Точка не найдена"}), 404

    # Обновляем только изменённое поле
    point[field] = value
    upsert_point(point)

    return jsonify({"status": "ok"})


@app.route("/add", methods=["POST"])
def add_point():
    data = request.json
    point = {
        "name": (data.get("name") or "Новая точка").strip(),
        "address": (data.get("address") or "").strip(),
        "phone": (data.get("phone") or "").strip(),
        "status": (data.get("status") or "в проработке").strip().lower(),
        "comment": (data.get("comment") or "").strip(),
        "updated_by": data.get("updated_by", "web")
    }
    upsert_point(point)
    return jsonify({"status": "ok"})


@app.route("/delete", methods=["POST"])
def delete():
    data = request.json
    point_id = int(data["id"])
    delete_point(point_id)
    return jsonify({"status": "ok"})


def open_browser():
    time.sleep(1.5)
    webbrowser.open_new("http://127.0.0.1:5000/")


if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    import os
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port, debug=False)   # debug=False в проде обязательно