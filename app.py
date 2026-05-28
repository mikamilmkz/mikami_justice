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


def clean_payload(data):
    return {
        key: value.strip() if isinstance(value, str) else value
        for key, value in (data or {}).items()
        if value not in ["", None]
    }


def split_full_name(value):
    parts = normalize_text(value).split()

    if len(parts) < 2:
        return "", ""

    prenom = parts[0]
    nom_famille = " ".join(parts[1:])
    return prenom, nom_famille


def normalize_search_data(data):
    """
    Permet aussi les erreurs de saisie du type :
    - prénom = "Julie Barret", nom vide
    - nom = "Julie Barret", prénom vide
    """
    payload = clean_payload(data)

    prenom = payload.get("prenom", "")
    nom_famille = payload.get("nom_famille", "")

    if prenom and not nom_famille:
        guessed_prenom, guessed_nom = split_full_name(prenom)
        if guessed_prenom and guessed_nom:
            payload["prenom"] = guessed_prenom
            payload["nom_famille"] = guessed_nom
            payload["query"] = prenom

    elif nom_famille and not prenom:
        guessed_prenom, guessed_nom = split_full_name(nom_famille)
        if guessed_prenom and guessed_nom:
            payload["prenom"] = guessed_prenom
            payload["nom_famille"] = guessed_nom
            payload["query"] = nom_famille

    return payload


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

    # Gros bonus si prénom + nom exacts, pour empêcher Julien/Barreteau de passer avant Julie/Barret.
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
        if key not in ["flexible", "query"] and value not in ["", None]
    }

    if not clean_query:
        return results

    return sorted(
        results,
        key=lambda item: (result_score(item, clean_query), get_confidence(item)),
        reverse=True,
    )


def result_identity_key(item):
    parts = [
        compact_text(get_item_value(item, "prenom")),
        compact_text(get_item_value(item, "nom_famille")),
        compact_text(get_item_value(item, "ville")),
        compact_text(item.get("date_naissance") or ""),
        digits_only(get_item_value(item, "telephone")),
        compact_text(get_item_value(item, "email")),
    ]

    key = "|".join(part for part in parts if part)

    if key:
        return key

    return compact_text(str(item))[:200]


def merge_results(result_groups):
    merged = []
    seen = set()

    for results in result_groups:
        for item in results:
            key = result_identity_key(item)

            if key in seen:
                continue

            seen.add(key)
            merged.append(item)

    return merged


def build_search_payloads(clean_data):
    """
    Ancien comportement : 1 seul appel flexible.
    Nouveau comportement : exact d'abord, puis flexible, puis recherche texte nom/prénom.
    Ça aide quand Brixhub cache le bon résultat dans une recherche trop floue.
    """
    base = dict(clean_data)
    base.pop("query", None)

    payloads = []

    def add(payload):
        cleaned = clean_payload(payload)
        marker = tuple(sorted(cleaned.items()))

        if marker not in [tuple(sorted(existing.items())) for existing in payloads]:
            payloads.append(cleaned)

    identity_fields = bool(base.get("prenom") or base.get("nom_famille"))
    has_city = bool(base.get("ville"))

    # 1) Exact d'abord pour éviter Julie Barret -> Julien Barreteau.
    if identity_fields:
        exact_payload = dict(base)
        exact_payload["flexible"] = False
        add(exact_payload)

    # 2) Recherche normale d'origine.
    flexible_payload = dict(base)
    flexible_payload["flexible"] = clean_data.get("flexible", True)
    add(flexible_payload)

    prenom = base.get("prenom", "")
    nom_famille = base.get("nom_famille", "")

    # 3) Recherche texte, très utile quand la recherche structurée nom/prénom est trop floue.
    if prenom and nom_famille:
        full_name_1 = f"{prenom} {nom_famille}".strip()
        full_name_2 = f"{nom_famille} {prenom}".strip()

        for full_name in [full_name_1, full_name_2]:
            add({"query": full_name, "flexible": False})
            add({"query": full_name, "flexible": True})

        # Si la ville est renseignée, on teste aussi nom + ville, car tu as vu que ça fonctionne bien.
        if has_city:
            ville = base.get("ville")
            add({"query": f"{full_name_1} {ville}", "flexible": False})
            add({"query": f"{full_name_1} {ville}", "flexible": True})

    # On limite pour ne pas faire trop attendre Discord/Render.
    return payloads[:8]


def call_brixhub(payload, timeout=35):
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
    data = normalize_search_data(request.json or {})

    result, status = call_brixhub(data)

    if not result.get("ok"):
        return jsonify({"error": result.get("error", "Erreur inconnue")}), status

    api_result = result["data"]
    results, meta = safe_results(api_result)
    sorted_results = sort_results(results, data)

    if isinstance(api_result.get("data"), dict):
        api_result["data"]["results"] = sorted_results

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

    payloads = [
        {"query": query, "flexible": False},
        {"query": query, "flexible": True},
    ]

    result_groups = []
    last_error = None

    for payload in payloads:
        result, status = call_brixhub(payload)

        if not result.get("ok"):
            last_error = result.get("error", "Erreur inconnue")
            continue

        api_result = result["data"]
        results, _meta = safe_results(api_result)
        result_groups.append(results)

    if not result_groups:
        return jsonify({"type": "error", "message": last_error or "Erreur inconnue"}), 502

    merged_results = merge_results(result_groups)
    sorted_results = sort_results(merged_results, {"query": query})

    history.append({
        "type": "bot-simple",
        "query": query,
        "total": len(sorted_results),
    })

    return jsonify({
        "type": "raw",
        "results": sorted_results,
        "total": len(sorted_results),
    })


@app.route("/api/multisearch", methods=["POST"])
def api_multisearch():
    clean_data = normalize_search_data(request.json or {})

    if not clean_data:
        return jsonify({"type": "raw", "results": [], "total": 0}), 400

    payloads = build_search_payloads(clean_data)
    result_groups = []
    searched_payloads = []
    last_error = None

    for payload in payloads:
        result, status = call_brixhub(payload)
        searched_payloads.append(payload)

        if not result.get("ok"):
            last_error = result.get("error", "Erreur inconnue")
            continue

        api_result = result["data"]
        results, _meta = safe_results(api_result)
        result_groups.append(results)

    if not result_groups:
        return jsonify({
            "type": "error",
            "message": last_error or "Erreur inconnue",
        }), 502

    merged_results = merge_results(result_groups)
    sorted_results = sort_results(merged_results, clean_data)

    history.append({
        "type": "bot",
        "query": clean_data,
        "payloads": searched_payloads,
        "total": len(sorted_results),
    })

    return jsonify({
        "type": "raw",
        "results": sorted_results,
        "total": len(sorted_results),
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
