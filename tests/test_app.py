from datetime import date, timedelta
from decimal import Decimal

import psycopg
import pytest

import app as app_module
from app import validate_card, validate_copy


# ---------- Card validation ----------

def valid_card_form(**overrides):
    """A form that should pass validation; tests change one field at a time."""
    form = {
        "set_id": "1",
        "card_number": "168",
        "card_name": "Lando Norris",
        "subset": "DriverCore",
        "team": "McLaren Mastercard Formula 1 Team",
        "variant": "Base",
        "print_run": "",
    }
    form.update(overrides)
    return form


def test_valid_card_has_no_errors():
    data, errors = validate_card(valid_card_form())
    assert errors == []
    assert data["set_id"] == 1
    assert data["print_run"] is None


def test_card_number_is_required():
    _, errors = validate_card(valid_card_form(card_number=""))
    assert "Card number is required." in errors


def test_team_not_on_list_is_rejected():
    _, errors = validate_card(valid_card_form(team="McLaren Mastercard Formula 1® Team"))
    assert "Choose a valid team." in errors


def test_print_run_zero_is_rejected():
    _, errors = validate_card(valid_card_form(variant="Gold", print_run="0"))
    assert "Print run must be a whole number above 0." in errors


# ---------- Copy validation ----------

NUMBERED_CARD = {"id": 5, "print_run": 50}
UNNUMBERED_CARD = {"id": 1, "print_run": None}


def test_serial_within_print_run_is_accepted():
    data, errors = validate_copy({"serial_number": "42"}, NUMBERED_CARD)
    assert errors == []
    assert data["serial_number"] == 42


def test_serial_above_print_run_is_rejected():
    _, errors = validate_copy({"serial_number": "51"}, NUMBERED_CARD)
    assert any("higher than the print run" in e for e in errors)


def test_serial_on_unnumbered_card_is_rejected():
    _, errors = validate_copy({"serial_number": "5"}, UNNUMBERED_CARD)
    assert any("isn't numbered" in e for e in errors)


def test_price_is_stored_as_exact_decimal():
    data, errors = validate_copy({"purchase_price": "4.50"}, UNNUMBERED_CARD)
    assert errors == []
    assert data["purchase_price"] == Decimal("4.50")


@pytest.mark.parametrize("bad_price", ["abc", "-1", "nan", "Infinity", "4.555"])
def test_invalid_prices_are_rejected(bad_price):
    _, errors = validate_copy({"purchase_price": bad_price}, UNNUMBERED_CARD)
    assert any("Price must be" in e for e in errors)


def test_future_date_is_rejected():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    _, errors = validate_copy({"date_acquired": tomorrow}, UNNUMBERED_CARD)
    assert "Date acquired can't be in the future." in errors

def test_serial_equal_to_print_run_is_accepted():
    """Edge case: 50/50 is a valid serial number."""
    _, errors = validate_copy({"serial_number": "50"}, NUMBERED_CARD)
    assert errors == []

# ---------- Health endpoint ----------

def test_health_returns_503_when_database_is_down(monkeypatch):
    def broken_db():
        raise psycopg.OperationalError("simulated outage")

    monkeypatch.setattr(app_module, "get_db", broken_db)
    client = app_module.app.test_client()

    response = client.get("/health")

    assert response.status_code == 503
    assert response.get_json() == {"status": "error", "database": "unreachable"}
