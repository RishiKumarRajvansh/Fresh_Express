"""Server-side replacements for small client-side utilities.

This module implements a few pure functions originally used in JS
that are safe to run on the server: email/phone/zip validators and
currency formatting.
"""
import re
import locale

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^[6-9]\d{9}$")
ZIP_RE = re.compile(r"^\d{6}$")


def validate_email(email: str) -> bool:
    if not isinstance(email, str):
        return False
    return bool(EMAIL_RE.match(email))


def validate_phone(phone: str) -> bool:
    if not isinstance(phone, str):
        return False
    return bool(PHONE_RE.match(phone))


def validate_zip(zip_code: str) -> bool:
    if not isinstance(zip_code, str):
        return False
    return bool(ZIP_RE.match(zip_code))


def format_currency_inr(amount) -> str:
    """Format number as INR currency similar to JS Intl.NumberFormat('en-IN', {currency: 'INR'})

    This uses locale if available, otherwise falls back to a basic formatting.
    """
    try:
        # Try to use locale-aware formatting
        locale.setlocale(locale.LC_ALL, 'en_IN.UTF-8')
        return locale.currency(amount, grouping=True, symbol=True)
    except Exception:
        # Fallback: basic formatting with INR symbol and two decimals
        try:
            return f"₹{float(amount):,.2f}"
        except Exception:
            return str(amount)
