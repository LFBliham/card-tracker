import psycopg
from psycopg.rows import dict_row
from flask import Flask, render_template

app = Flask(__name__)


def get_db():
    # Connection details come from PGHOST, PGUSER, PGPASSWORD, etc. in the environment
    return psycopg.connect(row_factory=dict_row)


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
