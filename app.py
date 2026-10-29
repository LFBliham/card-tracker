import psycopg
from psycopg.rows import dict_row
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# Allowed variants. Edit this list to match the real 2026 checklist.
VARIANTS = ["Base", "Green", "Gold", "Orange", "Red", "Superfractor", "Signed"]


def get_db():
    # Connection details come from PGHOST, PGUSER, PGPASSWORD, etc. in the environment
    return psycopg.connect(row_factory=dict_row)


def validate_card(form):
    """Check submitted form data. Returns (clean_data, list_of_errors)."""
    errors = []
    data = {
        "set_id": form.get("set_id", "").strip(),
        "card_number": form.get("card_number", "").strip(),
        "card_name": form.get("card_name", "").strip(),
        "subset": form.get("subset", "").strip() or None,
        "team": form.get("team", "").strip() or None,
        "variant": form.get("variant", "Base"),
        "print_run": form.get("print_run", "").strip() or None,
        "wishlisted": form.get("wishlisted") == "on",
    }

    if not data["set_id"].isdigit():
        errors.append("Choose a set.")
    else:
        data["set_id"] = int(data["set_id"])

    if not data["card_number"]:
        errors.append("Card number is required.")
    elif len(data["card_number"]) > 10:
        errors.append("Card number must be 10 characters or fewer.")

    if not data["card_name"]:
        errors.append("Card name is required.")
    elif len(data["card_name"]) > 100:
        errors.append("Card name must be 100 characters or fewer.")

    if data["variant"] not in VARIANTS:
        errors.append("Choose a valid variant.")

    if data["print_run"] is not None:
        if not data["print_run"].isdigit() or int(data["print_run"]) == 0:
            errors.append("Print run must be a whole number above 0.")
        else:
            data["print_run"] = int(data["print_run"])

    return data, errors


@app.route("/")
def index():
    with get_db() as conn:
        cards = conn.execute("""
            SELECT c.card_number, c.card_name, c.subset, c.team, c.variant,
                   count(o.id) AS copies
            FROM cards c
            LEFT JOIN owned_copies o ON o.card_id = c.id
            GROUP BY c.id
            ORDER BY c.card_number
        """).fetchall()
    return render_template("index.html", cards=cards)


@app.route("/cards/new", methods=["GET", "POST"])
def new_card():
    with get_db() as conn:
        sets = conn.execute("SELECT id, year, name FROM sets ORDER BY year DESC").fetchall()

        if request.method == "POST":
            data, errors = validate_card(request.form)
            if not errors:
                try:
                    with conn.transaction():
                        conn.execute("""
                            INSERT INTO cards (set_id, card_number, card_name, subset,
                                               team, variant, print_run, wishlisted)
                            VALUES (%(set_id)s, %(card_number)s, %(card_name)s, %(subset)s,
                                    %(team)s, %(variant)s, %(print_run)s, %(wishlisted)s)
                        """, data)
                    return redirect(url_for("index"))
                except psycopg.errors.UniqueViolation:
                    errors.append("That card number and variant already exist in this set.")
                except psycopg.errors.ForeignKeyViolation:
                    errors.append("That set doesn't exist.")

            return render_template("new_card.html", sets=sets, variants=VARIANTS,
                                   errors=errors, form=request.form), 400

    return render_template("new_card.html", sets=sets, variants=VARIANTS,
                           errors=[], form={})
