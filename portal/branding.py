import os

from flask import current_app

BRAND_DEFAULTS = {
    "site_name": "Client Portal",
    "tagline": "Secure file sharing",
    "logo": "",  # URL or data path
    "primary_color": "#2563eb",
    "accent_color": "#0ea5e9",
    "background_color": "#f8fafc",
    "card_color": "#ffffff",
    "text_color": "#0f172a",
    "welcome_title": "Welcome",
    "welcome_message": "Use the links below to download files. Contact us if you need help.",
    "footer_text": "Powered by Client Portal",
}


def get_branding():
    from . import db

    merged = dict(BRAND_DEFAULTS)
    stored = db.all_settings()
    for key in BRAND_DEFAULTS:
        if key in stored and stored[key]:
            merged[key] = stored[key]
    logo = merged.get("logo", "")
    if logo.startswith("/brand/") or logo.startswith("http"):
        merged["logo_uri"] = logo
    else:
        merged["logo_uri"] = ""
    return merged


def public_context(share=None):
    branding = get_branding()
    primary = branding["primary_color"]
    if share is not None and share["branding_color"]:
        primary = share["branding_color"]
    branding = dict(branding)
    branding["primary_color"] = primary
    return {"brand": branding}
