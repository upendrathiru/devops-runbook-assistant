"""
DevOps Runbook Assistant — API server.

Endpoints
---------
POST /api/session              -> create a new chat session
POST /api/chat                 -> ask a question, get a grounded answer + sources
POST /api/feedback              -> mark a prior answer helpful/not helpful
GET  /api/history/<session_id>  -> retrieve session history
POST /api/ingest/reindex        -> rebuild the retrieval index from data/runbooks
GET  /api/metrics               -> basic usage metrics
GET  /api/logs/export           -> CSV export of the audit log
GET  /healthz                   -> health check

Run with:  python app.py   (dev server on http://localhost:8000)
"""
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify, Response, send_from_directory

from config import REQUIRE_AUTH_HEADER
from retrieval import get_index
from llm import get_llm_provider
import storage

app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    # Allows the standalone frontend (possibly a different origin/port) to
    # call this API. Tighten to your actual internal frontend origin in
    # production instead of "*".
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


storage.init_db()
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


def _check_auth():
    """
    Stand-in for real internal SSO/LDAP auth (per spec: 'Internal only access').
    In production this middleware would validate a session cookie / SSO token
    issued by the corporate identity provider behind the reverse proxy.
    """
    if not REQUIRE_AUTH_HEADER:
        return True
    return REQUIRE_AUTH_HEADER in request.headers


@app.before_request
def auth_gate():
    if request.path.startswith("/api/") and not _check_auth():
        return jsonify({"error": "unauthorized"}), 401


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/api/session", methods=["POST"])
def create_session():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "anonymous")
    session_id = storage.create_session(user_id)
    return jsonify({"session_id": session_id, "user_id": user_id})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    session_id = data.get("session_id", "")
    user_id = data.get("user_id", "anonymous")

    if not question:
        return jsonify({"error": "question is required"}), 400

    start = time.time()
    index = get_index()
    results = index.search(question)
    chunks = [c for c, _score in results]

    provider = get_llm_provider()
    answer = provider.generate(question, chunks)
    latency_ms = int((time.time() - start) * 1000)

    sources = [
        {
            "title": c.source_title,
            "section": c.section,
            "path": os.path.relpath(c.source_path),
            "score": round(score, 3),
        }
        for c, score in results
    ]
    sources_str = "; ".join(f"{s['title']} > {s['section']}" for s in sources)

    query_id = storage.log_query(session_id, user_id, question, answer, sources_str, latency_ms)

    return jsonify({
        "query_id": query_id,
        "answer": answer,
        "sources": sources,
        "latency_ms": latency_ms,
    })


@app.route("/api/feedback", methods=["POST"])
def feedback():
    data = request.get_json(silent=True) or {}
    query_id = data.get("query_id")
    value = data.get("feedback")  # "up" or "down"
    if value not in ("up", "down"):
        return jsonify({"error": "feedback must be 'up' or 'down'"}), 400
    ok = storage.set_feedback(query_id, value)
    if not ok:
        return jsonify({"error": "query_id not found"}), 404
    return jsonify({"status": "recorded"})


@app.route("/api/history/<session_id>", methods=["GET"])
def history(session_id):
    return jsonify(storage.get_session_history(session_id))


@app.route("/api/ingest/reindex", methods=["POST"])
def reindex():
    index = get_index(rebuild=True)
    return jsonify({"status": "reindexed", "chunk_count": len(index.chunks)})


@app.route("/api/metrics", methods=["GET"])
def metrics():
    return jsonify(storage.get_metrics())


@app.route("/api/logs/export", methods=["GET"])
def export_logs():
    csv_data = storage.export_logs_csv()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )


# --- Serve the static frontend (dev convenience; use a real static host / CDN in prod) ---
@app.route("/")
def serve_frontend():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def serve_frontend_assets(filename):
    return send_from_directory(FRONTEND_DIR, filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
