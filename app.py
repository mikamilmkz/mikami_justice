from difflib import SequenceMatcher
import os
import re
import unicodedata

import requests
from flask import Flask, jsonify, render_template, request


app = Flask(__name__)

API_KEY = os.getenv("API_KEY")
BASE_URL = "https://brixhub.site/api/v1"
history = []


FIELD_ALIASES = {
    "prenom": ["prenom", "first_name", "firstname", "given_name"],
    "nom_famille": ["nom_famille", "nom", "last_name", "lastname", "surname", "family_name"],
    "ville": ["ville", "city"],
    "email": ["email", "mail"],
    "telephone": ["telephone", "mobile", "tel", "phone"],
    "nom_utilisateur": ["nom_utilisateur", "username", "user", "pseudo"],
}


@app.route("/")
def index():
    return render_template("index.html")


def get_headers():
    return {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json",
    }


def safe_results(result):
    data_block = result.get("data") or {}
    results = data_block.get("results") or []
    meta = result.get("meta") or {}
    return results, meta


def normalize_text(value):
    if value is None:
        return ""

    text = str(value).lower().strip()
    text = "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    text = re.sub(r"[^a-z0-9@.+]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def compact_text(value):
    return re.sub(r"[^a-z0-9]+", "", normalize_text(value))


def digits_only(value):
    return re.sub(r"\D+", "", str(value or ""))


def get_item_value(item, field_name):
    for key in FIELD_ALIASES.get(field_name, [field_name]):
        value = item.get(key)
        if value not in [None, "", "N/A"]:
            return value
    return ""


def basic_match_score(query_value, item_value):
    query = normalize_text(query_value)
    candidate = normalize_text(item_value)

    if not query or not candidate:
        return 0

    if query == candidate:
        return 100

    query_compact = compact_text(query)
    candidate_compact = compact_text(candidate)

    if query_compact and query_compact == candidate_compact:
        return 96

    if candidate.startswith(query):
        return 88

    if f" {query} " in f" {candidate} ":
        return 82

    if query in candidate:
        return 70

    ratio = SequenceMatcher(None, query, candidate).ratio()
    return int(ratio * 65)


def phone_match_score(query_value, item_value):
    query = digits_only(query_value)
    candidate = digits_only(item_value)

    if not query or not candidate:
        return 0

    if query == candidate:
        return 100

    if candidate.endswith(query) or query.endswith(candidate):
        return 85

    ratio = SequenceMatcher(None, query, candidate).ratio()
    return int(ratio * 60)


def get_confidence(item):
    try:
        return int(item.get("_confidence") or 0)
    except Exception:
        return 0


def full_name_score(query_data, item):
    query_first = query_data.get("prenom", "")
    query_last = query_data.get("nom_famille", "")

    if not query_first or not query_last:
        return 0

    query_variants = [
        f"{query_first} {query_last}",
        f"{query_last} {query_first}",
    ]

    item_first = get_item_value(item, "prenom")
    item_last = get_item_value(item, "nom_famille")

    item_variants = [
        f"{item_first} {item_last}".strip(),
        f"{item_last} {item_first}".strip(),
        item.get("nom_complet") or "",
        item.get("full_name") or "",
        item.get("name") or "",
    ]

    best = 0

    for query_variant in query_variants:
        for item_variant in item_variants:
            best = max(best, basic_match_score(query_variant, item_variant))

    return best * 10


def result_score(item, query_data):
    score = full_name_score(query_data, item)

    weights = {
        "prenom": 4,
        "nom_famille": 4,
        "ville": 2,
        "email": 5,
        "telephone": 5,
        "nom_utilisateur": 4,
    }

    for field_name, weight in weights.items():
        query_value = query_data.get(field_name)

        if not query_value:
            continue

        item_value = get_item_value(item, field_name)

        if field_name == "telephone":
            score += phone_match_score(query_value, item_value) * weight
        else:
            score += basic_match_score(query_value, item_value) * weight

    return score


def sort_results(results, query_data):
    clean_query = {
        key: value
        for key, value in (query_data or {}).items()
        if key != "flexible" and value not in ["", None]
    }

    if not clean_query:
        return results

    return sorted(
        results,
        key=lambda item: (result_score(item, clean_query), get_confidence(item)),
        reverse=True,
    )


def replace_results(api_result, sorted_results):
    if isinstance(api_result.get("data"), dict):
        api_result["data"]["results"] = sorted_results
    return api_result


def call_brixhub(payload, timeout=45):
    if not API_KEY:
        return {"ok": False, "error": "API_KEY manquante côté serveur."}, 500

    try:
        response = requests.post(
            f"{BASE_URL}/search",
            json=payload,
            headers=get_headers(),
            timeout=timeout,
        )
        response.raise_for_status()
        result = response.json()
        return {"ok": True, "data": result}, 200

    except requests.exceptions.Timeout:
        return {"ok": False, "error": "⏳ API Brixhub trop lente, réessaie dans quelques secondes."}, 504

    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": f"Erreur réseau API : {str(e)}"}, 502

    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


@app.route("/search", methods=["POST"])
def search():
    data = request.json or {}

    result, status = call_brixhub(data)

    if not result.get("ok"):
        return jsonify({"error": result.get("error", "Erreur inconnue")}), status

    api_result = result["data"]
    results, meta = safe_results(api_result)
    sorted_results = sort_results(results, data)
    api_result = replace_results(api_result, sorted_results)

    history.append({
        "type": "site",
        "query": data,
        "total": meta.get("total", len(sorted_results)),
    })

    return jsonify(api_result)


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()

    if not query:
        return jsonify({"type": "raw", "results": [], "total": 0}), 400

    payload = {
        "query": query,
        "flexible": True,
    }

    result, status = call_brixhub(payload)

    if not result.get("ok"):
        return jsonify({
            "type": "error",
            "message": result.get("error", "Erreur inconnue"),
        }), status

    api_result = result["data"]
    results, meta = safe_results(api_result)
    sorted_results = sort_results(results, payload)

    history.append({
        "type": "bot-simple",
        "query": payload,
        "total": meta.get("total", len(sorted_results)),
    })

    return jsonify({
        "type": "raw",
        "results": sorted_results,
        "total": meta.get("total", len(sorted_results)),
    })


@app.route("/api/multisearch", methods=["POST"])
def api_multisearch():
    data = request.json or {}
    clean_data = {
        key: value
        for key, value in data.items()
        if value not in ["", None]
    }

    if not clean_data:
        return jsonify({"type": "raw", "results": [], "total": 0}), 400

    result, status = call_brixhub(clean_data)

    if not result.get("ok"):
        return jsonify({
            "type": "error",
            "message": result.get("error", "Erreur inconnue"),
        }), status

    api_result = result["data"]
    results, meta = safe_results(api_result)
    sorted_results = sort_results(results, clean_data)

    history.append({
        "type": "bot",
        "query": clean_data,
        "total": meta.get("total", len(sorted_results)),
    })

    return jsonify({
        "type": "raw",
        "results": sorted_results,
        "total": meta.get("total", len(sorted_results)),
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "service": "MIKAMI OSINT API",
    })


@app.route("/history")
def get_history():
    return jsonify(history)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
