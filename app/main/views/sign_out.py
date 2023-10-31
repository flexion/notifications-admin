import os

import requests
from flask import current_app, redirect, url_for
from flask_login import current_user

from app.main import main

# import uuid

def _sign_out_at_login_dot_gov():
    base_url = "https://idp.int.identitysandbox.gov/openid_connect/logout?"
    client_id = f"client_id={os.getenv('LOGIN_DOT_GOV_CLIENT_ID')}"
    post_logout_redirect_uri = "post_logout_redirect_uri=http://localhost:6012/sign-in"

    # TODO If I take this url and put it in the browser, login.gov sign out works properly
    # TODO But with this code it results in a 404 error message and we don't sign out from login.gov
    url = f"{base_url}{client_id}&{post_logout_redirect_uri}"
    current_app.logger.info(f"url={url}")
    response = requests.post(url, headers={"User-Agent": "Custom"})
    current_app.logger.info(f"login.gov response: {response.text}")


@main.route("/sign-out", methods=(["GET", "POST"]))
def sign_out():
    # An AnonymousUser does not have an id
    if current_user.is_authenticated:
        current_user.sign_out()
        _sign_out_at_login_dot_gov()
    return redirect(url_for("main.index"))
