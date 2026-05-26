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


def get_headers():
    return {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }


def safe_results(result):
    data_block = result.get("data") or {}
    results = data_block.get("results") or []
    meta = result.get("meta") or {}

    return results, meta


def call_brixhub(payload, timeout=45):
    if not API_KEY:
        return {
            "ok": False,
            "error": "API_KEY manquante côté serveur."
        }, 500

    try:
        response = requests.post(
            f"{BASE_URL}/search",
            json=payload,
            headers=get_headers(),
            timeout=timeout
        )

        response.raise_for_status()
        result = response.json()

        return {
            "ok": True,
            "data": result
        }, 200

    except requests.exceptions.Timeout:
        return {
            "ok": False,
            "error": "⏳ API Brixhub trop lente, réessaie dans quelques secondes."
        }, 504

    except requests.exceptions.RequestException as e:
        return {
            "ok": False,
            "error": f"Erreur réseau API : {str(e)}"
        }, 502

    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }, 500


@app.route("/search", methods=["POST"])
def search():
    data = request.json or {}

    result, status = call_brixhub(data)

    if not result.get("ok"):
        return jsonify({
            "error": result.get("error", "Erreur inconnue")
        }), status

    api_result = result["data"]
    results, meta = safe_results(api_result)

    history.append({
        "type": "site",
        "query": data,
        "total": meta.get("total", len(results))
    })

    return jsonify(api_result)


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()

    if not query:
        return jsonify({
            "type": "raw",
            "results": [],
            "total": 0
        }), 400

    payload = {
        "query": query,
        "flexible": True
    }

    result, status = call_brixhub(payload)

    if not result.get("ok"):
        return jsonify({
            "type": "error",
            "message": result.get("error", "Erreur inconnue")
        }), status

    api_result = result["data"]
    results, meta = safe_results(api_result)

    history.append({
        "type": "bot-simple",
        "query": payload,
        "total": meta.get("total", len(results))
    })

    return jsonify({
        "type": "raw",
        "results": results,
        "total": meta.get("total", len(results))
    })


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

    result, status = call_brixhub(clean_data)

    if not result.get("ok"):
        return jsonify({
            "type": "error",
            "message": result.get("error", "Erreur inconnue")
        }), status

    api_result = result["data"]
    results, meta = safe_results(api_result)

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


@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "service": "MIKAMI OSINT API"
    })


@app.route("/history")
def get_history():
    return jsonify(history)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)