from flask import Flask, render_template, request, jsonify
import requests
import os

app = Flask(__name__)

API_KEY = os.getenv("API_KEY")
BASE_URL = "https://brixhub.site/api/v1"

history = []


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search", methods=["POST"])
def search():
    data = request.json or {}

    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            f"{BASE_URL}/search",
            json=data,
            headers=headers,
            timeout=45
        )

        result = response.json()

        data_block = result.get("data") or {}
        results = data_block.get("results") or []
        meta = result.get("meta") or {}

        history.append({
            "type": "site",
            "query": data,
            "total": meta.get("total", len(results))
        })

        return jsonify(result)

    except requests.exceptions.Timeout:
        return jsonify({
            "error": "⏳ API Brixhub trop lente, réessaie dans quelques secondes."
        }), 504

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.route("/api/multisearch", methods=["POST"])
def api_multisearch():
    data = request.json or {}

    clean_data = {
        k: v for k, v in data.items()
        if v not in ["", None]
    }

    if not clean_data:
        return jsonify({
            "type": "raw",
            "results": [],
            "total": 0
        }), 400

    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            f"{BASE_URL}/search",
            json=clean_data,
            headers=headers,
            timeout=45
        )

        result = response.json()

        data_block = result.get("data") or {}
        results = data_block.get("results") or []
        meta = result.get("meta") or {}

        history.append({
            "type": "bot",
            "query": clean_data,
            "total": meta.get("total", len(results))
        })

        return jsonify({
            "type": "raw",
            "results": results,
            "total": meta.get("total", len(results))
        })

    except requests.exceptions.Timeout:
        return jsonify({
            "type": "error",
            "message": "⏳ API Brixhub trop lente, réessaie dans quelques secondes."
        }), 504

    except Exception as e:
        return jsonify({
            "type": "error",
            "message": str(e)
        }), 500


@app.route("/history")
def get_history():
    return jsonify(history)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)