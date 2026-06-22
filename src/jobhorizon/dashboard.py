import io
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_from_directory

from jobhorizon import criteria as criteria_mod
from jobhorizon import db, features, tailoring
from jobhorizon.config import load_config
from jobhorizon.paths import OUTPUTS_DIR

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

EXPORT_COLUMNS = [
    "job_id",
    "title",
    "company",
    "source",
    "location",
    "work_type",
    "gate_passed",
    "gate_reason",
    "score",
    "model_source",
    "skills_matched",
    "skills_matched_list",
    "domain_hits",
    "domain_matched_list",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_min_inr",
    "salary_max_inr",
    "url",
    "external_id",
    "poster_name",
    "poster_email",
    "posted_date",
    "status",
]


def create_app() -> Flask:
    app = Flask(__name__, template_folder=str(TEMPLATES_DIR))

    @app.route("/")
    def index():
        conn = db.get_connection()
        db.init_db(conn)
        criteria = criteria_mod.load_active_criteria(conn)
        conn.close()
        return render_template("index.html", criteria=criteria)

    @app.route("/api/jobs")
    def api_jobs():
        tab = request.args.get("tab", "kept")
        if tab not in ("kept", "discarded"):
            return jsonify({"error": "tab must be 'kept' or 'discarded'"}), 400

        conn = db.get_connection()
        criteria = criteria_mod.load_active_criteria(conn)
        default_threshold = criteria.score_threshold if criteria else 0.0
        threshold = float(request.args.get("threshold", default_threshold))
        rows = db.fetch_jobs_for_tab(conn, tab, threshold)
        conn.close()
        return jsonify(rows)

    @app.route("/api/mark", methods=["POST"])
    def api_mark():
        payload = request.get_json(force=True) or {}
        job_id = payload.get("job_id")
        if not job_id or "relevant" not in payload:
            return jsonify({"error": "job_id and relevant are required"}), 400

        relevant = bool(payload["relevant"])
        from_discard = bool(payload.get("from_discard", False))
        status = "relevant" if relevant else "irrelevant"

        conn = db.get_connection()
        try:
            db.update_review_status(conn, job_id, status, from_discard)
            features.record_label(conn, job_id, relevant, from_discard, load_config())
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 404
        finally:
            conn.close()
        return jsonify({"ok": True})

    @app.route("/api/threshold", methods=["POST"])
    def api_threshold():
        payload = request.get_json(force=True) or {}
        if "value" not in payload:
            return jsonify({"error": "value is required"}), 400

        conn = db.get_connection()
        criteria = criteria_mod.load_active_criteria(conn)
        if criteria is None:
            conn.close()
            return jsonify({"error": "no active criteria"}), 400
        db.update_score_threshold(conn, criteria.id, float(payload["value"]))
        conn.close()
        return jsonify({"ok": True})

    @app.route("/api/update-criteria", methods=["POST"])
    def api_update_criteria():
        payload = request.get_json(force=True) or {}
        conn = db.get_connection()
        has_existing = criteria_mod.load_active_criteria(conn) is not None
        if has_existing and not payload.get("confirm"):
            conn.close()
            return jsonify({"error": "confirm is required to update criteria"}), 400

        db.clear_corpus(conn, also_clear_labels=bool(payload.get("full_reset", False)))
        criteria = criteria_mod.Criteria(
            titles=payload.get("titles", []),
            skills=payload.get("skills", []),
            location=payload.get("location", ""),
            working_mode=payload.get("working_mode", "any"),
            pay_min=float(payload.get("pay_min", 0)),
            pay_currency=payload.get("pay_currency", "INR"),
            domain_keywords=payload.get("domain_keywords", [])[:10],
        )
        criteria_mod.save_criteria(conn, criteria)
        conn.close()
        return jsonify({"ok": True})

    @app.route("/api/export.csv")
    def api_export_csv():
        conn = db.get_connection()
        rows = db.fetch_all_jobs_for_export(conn)
        conn.close()

        buf = io.StringIO()
        buf.write(",".join(EXPORT_COLUMNS) + "\n")
        for row in rows:
            values = []
            for col in EXPORT_COLUMNS:
                val = row.get(col, "")
                if col in ("skills_matched_list", "domain_matched_list"):
                    val = "|".join(val or [])
                text = "" if val is None else str(val)
                values.append('"' + text.replace('"', '""') + '"')
            buf.write(",".join(values) + "\n")

        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=jobhorizon_export.csv"},
        )

    @app.route("/api/tailor", methods=["POST"])
    def api_tailor():
        payload = request.get_json(force=True) or {}
        job_id = payload.get("job_id")
        if not job_id:
            return jsonify({"error": "job_id is required"}), 400

        conn = db.get_connection()
        try:
            report = tailoring.tailor_job(conn, job_id, load_config())
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            return jsonify({"error": str(exc)}), 400
        finally:
            conn.close()
        return jsonify(report)

    @app.route("/api/tailored")
    def api_tailored():
        job_id = request.args.get("job_id")
        if not job_id:
            return jsonify({"error": "job_id is required"}), 400
        conn = db.get_connection()
        rows = db.fetch_tailored_resumes(conn, job_id)
        conn.close()
        return jsonify(rows)

    @app.route("/outputs/<path:filename>")
    def serve_output(filename):
        return send_from_directory(OUTPUTS_DIR, filename, as_attachment=True)

    return app


def main() -> None:
    app = create_app()
    app.run(host="127.0.0.1", port=5000)


if __name__ == "__main__":
    main()
