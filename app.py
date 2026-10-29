from datetime import date
from decimal import Decimal, InvalidOperation

import psycopg
from psycopg.rows import dict_row
from flask import Flask, render_template, request, redirect, url_for, abort

app = Flask(__name__)

# Allowed variants. Edit this list to match the real 2026 checklist.
VARIANTS = ["Base", "Green", "Gold", "Orange", "Red", "Superfractor", "Signed"]
CONDITIONS = ["mint", "near_mint", "excellent", "good", "fair", "poor"]

SUBSETS = [
    # Main collection
    "F1 Team Logos",
    "2026 F1 Team Principals",
    "2026 F1 Dynamic Duos",
    "2026 F1 Hero",
    "Power In Numbers",
    "Lightning Lids",
    "Epic Moments",
    "Speed Silhouettes",
    "Legends Of The Grid",
    "2025 F1 Sprint Superstars",
    "DriverCore",
    "Night Shift",
    "2026 F1 Car",
    "La Monumental",
    "F1 Turbo Attax Legacy",
    "Champions",
    "10 Years Of F2 - Most Successful",
    "F2 One To Watch",
    "Technical Drawing",
    "Signature Style",
    "100 Club",
    "100 Club - Legend",
    "Black Edge",
    "Diamond Infinity",
    "Turbo Chrome",
    "The Winning Formula",
    "Strategy Card",
    "F1 Gold",

    # Special editions and exclusives
    "Guardians Of The Grid",
    "Sunshine State",
    "Greats Of The Grid",
    "Limited Editions",
    "Black Gold Limited Edition",
    "Manufactured Relics",
    "Raceday Relics",
]

TEAMS = [
    # 2026 Formula 1 teams
    "McLaren Mastercard Formula 1 Team",
    "Mercedes-AMG PETRONAS Formula 1 Team",
    "Oracle Red Bull Racing",
    "Scuderia Ferrari HP",
    "Atlassian Williams F1 Team",
    "VISA Cash App Racing Bulls Formula One Team",
    "Aston Martin Aramco Formula One Team",
    "TGR Haas F1 Team",
    "Audi Revolut F1 Team",
    "BWT Alpine Formula One Team",
    "Cadillac Formula 1 Team",

    # Historical team featured on 2026 cards
    "KICK Sauber F1 Team",

    # Formula 2 teams featured in the collection
    "Invicta Racing",
    "Trident",
    "MP Motorsport",
    "Hitech TGR",
    "Campos Racing",
    "DAMS Lucas Oil",
    "PREMA Racing",
    "Rodin Motorsport",
    "ART Grand Prix",
    "AIX Racing",
    "Van Amersfoort Racing",
]


def get_db():
    # Connection details come from PGHOST, PGUSER, PGPASSWORD, etc. in the environment
    return psycopg.connect(row_factory=dict_row, connect_timeout=3)


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

    if data["subset"] is not None and data["subset"] not in SUBSETS:
        errors.append("Choose a valid subset.")

    if data["team"] is not None and data["team"] not in TEAMS:
        errors.append("Choose a valid team.")

    if data["variant"] not in VARIANTS:
        errors.append("Choose a valid variant.")

    if data["print_run"] is not None:
        if not data["print_run"].isdigit() or int(data["print_run"]) == 0:
            errors.append("Print run must be a whole number above 0.")
        else:
            data["print_run"] = int(data["print_run"])

    return data, errors


def validate_copy(form, card):
    """Check a submitted owned-copy form against the card it belongs to."""
    errors = []
    data = {
        "card_id": card["id"],
        "condition": form.get("condition", "").strip() or None,
        "serial_number": form.get("serial_number", "").strip() or None,
        "storage": form.get("storage", "").strip() or None,
        "purchase_price": form.get("purchase_price", "").strip() or None,
        "purchased_from": form.get("purchased_from", "").strip() or None,
        "date_acquired": form.get("date_acquired", "").strip() or None,
        "notes": form.get("notes", "").strip() or None,
    }

    if data["condition"] is not None and data["condition"] not in CONDITIONS:
        errors.append("Choose a valid condition.")

    # The cross-table rule the database can't check with a CHECK constraint
    if data["serial_number"] is not None:
        if not data["serial_number"].isdigit() or int(data["serial_number"]) == 0:
            errors.append("Serial number must be a whole number above 0.")
        elif card["print_run"] is None:
            errors.append("This card isn't numbered, so it can't have a serial number.")
        elif int(data["serial_number"]) > card["print_run"]:
            errors.append(f"Serial number can't be higher than the print run (/{card['print_run']}).")
        else:
            data["serial_number"] = int(data["serial_number"])

    if data["purchase_price"] is not None:
        try:
            price = Decimal(data["purchase_price"])
        except InvalidOperation:
            price = None
        if (price is None or not price.is_finite() or price < 0
                or price >= 1_000_000 or price.as_tuple().exponent < -2):
            errors.append("Price must be between 0 and 999999.99, with at most 2 decimal places.")
        else:
            data["purchase_price"] = price

    if data["date_acquired"] is not None:
        try:
            acquired = date.fromisoformat(data["date_acquired"])
        except ValueError:
            errors.append("Date must be in YYYY-MM-DD format.")
        else:
            if acquired > date.today():
                errors.append("Date acquired can't be in the future.")
            else:
                data["date_acquired"] = acquired

    for field, limit in [("storage", 100), ("purchased_from", 100), ("notes", 1000)]:
        if data[field] and len(data[field]) > limit:
            label = field.replace("_", " ").capitalize()
            errors.append(f"{label} must be {limit} characters or fewer.")

    return data, errors


@app.route("/")
def index():
    with get_db() as conn:
        cards = conn.execute("""
            SELECT c.id, c.card_number, c.card_name, c.subset, c.team, c.variant,
                   count(o.id) AS copies
            FROM cards c
            LEFT JOIN owned_copies o ON o.card_id = c.id
            GROUP BY c.id
            ORDER BY c.card_number
        """).fetchall()
    return render_template("index.html", cards=cards)

@app.route("/health")
def health():
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
    except psycopg.Error as e:
        app.logger.error("Health check failed: database unreachable: %s", e)
        return {"status": "error", "database": "unreachable"}, 503
    return {"status": "ok", "database": "ok"}, 200
    
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
                                   subsets=SUBSETS, teams=TEAMS,
                                   errors=errors, form=request.form), 400

    return render_template("new_card.html", sets=sets, variants=VARIANTS,
                           subsets=SUBSETS, teams=TEAMS,
                           errors=[], form={})


@app.route("/cards/<int:card_id>/copies/new", methods=["GET", "POST"])
def new_copy(card_id):
    with get_db() as conn:
        card = conn.execute(
            "SELECT id, card_number, card_name, variant, print_run FROM cards WHERE id = %s",
            (card_id,),
        ).fetchone()
        if card is None:
            abort(404)

        if request.method == "POST":
            data, errors = validate_copy(request.form, card)
            if not errors:
                conn.execute("""
                    INSERT INTO owned_copies (card_id, condition, serial_number, storage,
                                              purchase_price, purchased_from, date_acquired, notes)
                    VALUES (%(card_id)s, %(condition)s, %(serial_number)s, %(storage)s,
                            %(purchase_price)s, %(purchased_from)s, %(date_acquired)s, %(notes)s)
                """, data)
                return redirect(url_for("index"))

            return render_template("new_copy.html", card=card, conditions=CONDITIONS,
                                   errors=errors, form=request.form), 400

    return render_template("new_copy.html", card=card, conditions=CONDITIONS,
                           errors=[], form={})
