from flask import Flask, render_template, request, jsonify
import requests
import os

app = Flask(__name__)

API_KEY = os.getenv("API_KEY")
BASE_URL = "https://brixhub.site/api/v1"

# 🔥 HISTORIQUE EN MÉMOIRE
history = []

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search", methods=["POST"])
def search():
    data = request.json

    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            f"{BASE_URL}/search",
            json=data,
            headers=headers
        )

        result = response.json()

        # 🔥 SAUVEGARDE
        history.append({
            "query": data,
            "result": result
        })

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})

# 🔥 ROUTE HISTORIQUE
@app.route("/history")
def get_history():
    return jsonify(history)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
