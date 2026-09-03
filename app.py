"""Flask app: HORECA competition lens.

Enter an address + category, see the 5 closest matching OSM establishments
within 1 km, and generate a Quarto PDF report of the analysis.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_file, url_for

from analysis import assess_competition
from osm_client import GeocodeError, find_establishments, geocode

app = Flask(__name__)
app.secret_key = "dev-only-secret-key"  # fine for local use, not for production

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

RADIUS_M = 1000
CATEGORIES = ["cafe", "restaurant", "hotel"]


def find_quarto():
    """Return the configured Quarto executable, if it is available."""
    configured_path = os.environ.get("QUARTO_BIN")
    if configured_path:
        return configured_path if Path(configured_path).exists() else None

    on_path = shutil.which("quarto")
    if on_path:
        return on_path

    windows_install = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Quarto" / "bin" / "quarto.exe"
    return str(windows_install) if windows_install.exists() else None


def find_python():
    """Return the project interpreter used for Quarto's Jupyter kernel."""
    project_python = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    return str(project_python) if project_python.exists() else sys.executable


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", categories=CATEGORIES)


@app.route("/search", methods=["POST"])
def search():
    address = request.form.get("address", "").strip()
    category = request.form.get("category", "").strip()

    if not address or category not in CATEGORIES:
        flash("Please enter an address and pick a valid category.")
        return redirect(url_for("index"))

    try:
        lat, lon = geocode(address)
    except GeocodeError as exc:
        flash(str(exc))
        return redirect(url_for("index"))
    except Exception as exc:  # network / API issues
        flash(f"Could not look up that address: {exc}")
        return redirect(url_for("index"))

    try:
        places = find_establishments(lat, lon, category, RADIUS_M)
    except Exception as exc:
        flash(f"Could not query OpenStreetMap: {exc}")
        return redirect(url_for("index"))

    top5 = places[:5]
    closest_distance = places[0].distance_m if places else None
    assessment = assess_competition(len(places), closest_distance, category)

    result_data = {
        "address": address,
        "category": category,
        "radius_m": RADIUS_M,
        "lat": lat,
        "lon": lon,
        "match_count": len(places),
        "closest_distance_m": closest_distance,
        "assessment_level": assessment.level,
        "assessment_text": assessment.text,
        "top5": [
            {
                "name": p.name,
                "type": p.place_type,
                "website": p.website,
                "distance_m": round(p.distance_m, 1),
            }
            for p in top5
        ],
    }

    # Persist so /report can render a PDF without resubmitting the form.
    session_id = uuid.uuid4().hex[:8]
    data_path = DATA_DIR / f"{session_id}.json"
    data_path.write_text(json.dumps(result_data, indent=2))

    return render_template(
        "results.html",
        data=result_data,
        session_id=session_id,
        fewer_than_5=len(places) < 5,
    )


@app.route("/report/<session_id>", methods=["GET"])
def report(session_id):
    data_path = DATA_DIR / f"{session_id}.json"
    if not data_path.exists():
        flash("Search data expired or not found. Please search again.")
        return redirect(url_for("index"))

    qmd_path = BASE_DIR / "report.qmd"
    pdf_name = f"{session_id}.pdf"
    quarto = find_quarto()
    if not quarto:
        flash(
            "Quarto was not found. Add it to PATH or set QUARTO_BIN to the "
            "full path of the Quarto executable."
        )
        return redirect(url_for("index"))

    # IMPORTANT (Windows): Quarto parses -P values as YAML. Backslashes in
    # Windows paths (e.g. \data\, \Ai_taskforce...) can be misread as YAML
    # escape sequences and corrupt the path, causing a FileNotFoundError
    # inside the rendered notebook even though the file exists on disk.
    # Forward slashes are valid on Windows and safe in YAML, so we convert.
    data_file_arg = data_path.as_posix()
    render_environment = os.environ.copy()
    render_environment["QUARTO_PYTHON"] = find_python()

    with tempfile.TemporaryDirectory(prefix="quarto-", dir=BASE_DIR) as render_dir:
        cmd = [
            quarto,
            "render",
            str(qmd_path),
            "-P",
            f"data_file:{data_file_arg}",
            "-o",
            pdf_name,
            "--output-dir",
            render_dir,
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, env=render_environment
        )
        rendered_pdf = Path(render_dir) / pdf_name
        pdf_out = DATA_DIR / pdf_name
        if result.returncode == 0 and rendered_pdf.exists():
            shutil.move(str(rendered_pdf), pdf_out)

    if result.returncode != 0 or not pdf_out.exists():
        flash(
            "Quarto render failed. Check that Quarto (and the typst backend) is "
            "installed and on PATH. Details: " + result.stderr[-800:]
        )
        return redirect(url_for("index"))

    return send_file(pdf_out, as_attachment=True, download_name="horeca_report.pdf")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
