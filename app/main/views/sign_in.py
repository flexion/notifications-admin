import os
import time
import uuid

import jwt
import requests
from flask import (
    Markup,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user

from app import login_manager, user_api_client
from app.main import main
from app.main.forms import LoginForm
from app.main.views.verify import activate_user
from app.models.user import InvitedUser, User
from app.utils import hide_from_search_engines
from app.utils.login import is_safe_redirect_url


def _get_access_token(code, state):
    current_app.logger.info(
        f"HURRAY!  THIS IS REDIRECT FROM LOGIN DOT GOV AND WE HAVE CODE {code} and STATE {state}"
    )
    # TODO use the code to get the access_token with jwt
    # Using the access_token get the email from the user info
    # Use the call five lines down to look up the user from the email
    # activate the user and redirect as five lines down
    pemfile = open("./private.pem", "r")
    keystring = pemfile.read()
    pemfile.close()
    payload = {
        "iss": "urn:gov:gsa:openidconnect.profiles:sp:sso:gsa:test_notify_gov",
        "sub": "urn:gov:gsa:openidconnect.profiles:sp:sso:gsa:test_notify_gov",
        "aud": "https://idp.int.identitysandbox.gov/api/openid_connect/token",
        "jti": str(uuid.uuid4()),
        # JWT expiration time (10 minute maximum)
        "exp": int(time.time()) + (10 * 60),
    }

    jwt_instance = jwt.PyJWT()
    token = jwt_instance.encode(payload, keystring, algorithm="RS256")
    base_url = "https://idp.int.identitysandbox.gov/api/openid_connect/token?"
    cli_assert = f"client_assertion={token}"
    cli_assert_type = "client_assertion_type=urn%3Aietf%3Aparams%3Aoauth%3Aclient-assertion-type%3Ajwt-bearer"
    code_param = f"code={code}"
    url = f"{base_url}{cli_assert}&{cli_assert_type}&{code_param}&grant_type=authorization_code"
    headers = {"Authorization": "Bearer %s" % token}
    response = requests.post(url, headers=headers)
    current_app.logger.info(f"GOT A RESPONSE {response.json()}")
    access_token = response.json()["access_token"]
    current_app.logger.info(f"HURRAY GOT THE ACCESS TOKEN! {access_token}")
    return access_token


def _get_user_email(access_token):
    headers = {"Authorization": "Bearer %s" % access_token}
    user_attributes = requests.get(
        "https://idp.int.identitysandbox.gov/api/openid_connect/userinfo",
        headers=headers,
    )
    current_app.logger.info(f"HURRAY GOT USER ATTRIBUTES {user_attributes.json()}")
    user_email = user_attributes.json()["email"]
    return user_email


@main.route("/sign-in", methods=(["GET", "POST"]))
@hide_from_search_engines
def sign_in():
    # start login.gov
    code = request.args.get("code")
    state = request.args.get("state")
    login_gov_error = request.args.get("error")
    if code and state:
        access_token = _get_access_token(code, state)
        user_email = _get_user_email(access_token)
        redirect_url = request.args.get("next")

        # activate the user
        user = user_api_client.get_user_by_email(user_email)
        activate_user(user["id"])
        return redirect(url_for("main.show_accounts_or_dashboard", next=redirect_url))

    elif login_gov_error:
        current_app.logger.error(f"BOO!  GOT A LOGIN GOV ERROR {login_gov_error}")
        raise Exception(f"Could not login with login.gov {login_gov_error}")
    # end login.gov

    redirect_url = request.args.get("next")

    if os.getenv("NOTIFY_E2E_TEST_EMAIL"):
        user = user_api_client.get_user_by_email(os.getenv("NOTIFY_E2E_TEST_EMAIL"))
        activate_user(user["id"])
        return redirect(url_for("main.show_accounts_or_dashboard", next=redirect_url))

    if current_user and current_user.is_authenticated:
        if redirect_url and is_safe_redirect_url(redirect_url):
            return redirect(redirect_url)
        return redirect(url_for("main.show_accounts_or_dashboard"))

    form = LoginForm()
    password_reset_url = url_for(".forgot_password", next=request.args.get("next"))

    if form.validate_on_submit():
        user = User.from_email_address_and_password_or_none(
            form.email_address.data, form.password.data
        )

        if user:
            # add user to session to mark us as in the process of signing the user in
            session["user_details"] = {"email": user.email_address, "id": user.id}

            if user.state == "pending":
                return redirect(
                    url_for("main.resend_email_verification", next=redirect_url)
                )

            if user.is_active:
                if session.get("invited_user_id"):
                    invited_user = InvitedUser.from_session()
                    if user.email_address.lower() != invited_user.email_address.lower():
                        flash("You cannot accept an invite for another person.")
                        session.pop("invited_user_id", None)
                        abort(403)
                    else:
                        invited_user.accept_invite()

                user.send_login_code()

                if user.sms_auth:
                    return redirect(url_for(".two_factor_sms", next=redirect_url))

                if user.email_auth:
                    return redirect(
                        url_for(".two_factor_email_sent", next=redirect_url)
                    )

        # Vague error message for login in case of user not known, locked, inactive or password not verified
        flash(
            Markup(
                (
                    f"The email address or password you entered is incorrect."
                    f"&ensp;<a href={password_reset_url} class='usa-link'>Forgot your password?</a>"
                )
            )
        )

    other_device = current_user.logged_in_elsewhere()
    return render_template(
        "views/signin.html",
        form=form,
        again=bool(redirect_url),
        other_device=other_device,
        password_reset_url=password_reset_url,
    )


@login_manager.unauthorized_handler
def sign_in_again():
    return redirect(url_for("main.sign_in", next=request.path))
