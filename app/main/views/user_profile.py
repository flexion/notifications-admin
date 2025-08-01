import json

from flask import (
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

from app import user_api_client
from app.enums import AuthType
from app.event_handlers import (
    create_email_change_event,
    create_mobile_number_change_event,
)
from app.main import main
from app.main.forms import (
    ChangeEmailForm,
    ChangeMobileNumberForm,
    ChangeNameForm,
    ChangePasswordForm,
    ChangePreferredTimezoneForm,
    ConfirmPasswordForm,
    ServiceOnOffSettingForm,
    TwoFactorForm,
)
from app.models.user import User
from app.utils import hilite
from app.utils.user import user_is_gov_user, user_is_logged_in
from notifications_utils.url_safe_token import check_token

NEW_EMAIL = "new-email"
NEW_MOBILE = "new-mob"
NEW_MOBILE_PASSWORD_CONFIRMED = (
    "new-mob-password-confirmed"  # nosec B105 - this is not a password
)


@main.route("/user-profile")
@user_is_logged_in
def user_profile():
    return render_template(
        "views/user-profile.html",
        can_see_edit=current_user.is_gov_user,
    )


@main.route("/user-profile/name", methods=["GET", "POST"])
@user_is_logged_in
def user_profile_name():
    form = ChangeNameForm(new_name=current_user.name)

    if form.validate_on_submit():
        current_user.update(name=form.new_name.data)
        return redirect(url_for(".user_profile"))

    return render_template(
        "views/user-profile/change.html", thing="name", form_field=form.new_name
    )


@main.route("/user-profile/preferred_timezone", methods=["GET", "POST"])
@user_is_logged_in
def user_profile_preferred_timezone():
    form = ChangePreferredTimezoneForm(new_name=current_user.preferred_timezone)

    if form.validate_on_submit():
        current_user.update(preferred_timezone=form.new_preferred_timezone.data)
        current_user.preferred_timezone = form.new_preferred_timezone.data
        return redirect(url_for(".user_profile"))
    return render_template(
        "views/user-profile/change.html",
        thing="preferred timezone",
        form_field=form.new_preferred_timezone,
    )


@main.route("/user-profile/email", methods=["GET", "POST"])
@user_is_logged_in
@user_is_gov_user
def user_profile_email():
    form = ChangeEmailForm(
        User.already_registered, email_address=current_user.email_address
    )

    if form.validate_on_submit():
        session[NEW_EMAIL] = form.email_address.data
        return redirect(url_for(".user_profile_email_authenticate"))
    return render_template(
        "views/user-profile/change.html",
        thing="email address",
        form_field=form.email_address,
    )


@main.route("/user-profile/email/authenticate", methods=["GET", "POST"])
@user_is_logged_in
def user_profile_email_authenticate():
    # Validate password for form
    def _check_password(pwd):
        return user_api_client.verify_password(current_user.id, pwd)

    form = ConfirmPasswordForm(_check_password)

    if NEW_EMAIL not in session:
        return redirect("main.user_profile_email")

    if form.validate_on_submit():
        user_api_client.send_change_email_verification(
            current_user.id, session[NEW_EMAIL]
        )
        create_email_change_event(
            user_id=current_user.id,
            updated_by_id=current_user.id,
            original_email_address=current_user.email_address,
            new_email_address=session[NEW_EMAIL],
        )
        return render_template(
            "views/change-email-continue.html", new_email=session[NEW_EMAIL]
        )

    return render_template(
        "views/user-profile/authenticate.html",
        thing="email address",
        form=form,
        back_link=url_for(".user_profile_email"),
    )


@main.route("/user-profile/email/confirm/<token>", methods=["GET"])
@user_is_logged_in
def user_profile_email_confirm(token):
    token_data = check_token(
        token,
        current_app.config["SECRET_KEY"],
        current_app.config["DANGEROUS_SALT"],
        current_app.config["EMAIL_EXPIRY_SECONDS"],
    )
    token_data = json.loads(token_data)
    user = User.from_id(token_data["user_id"])
    user.update(email_address=token_data["email"])
    session.pop(NEW_EMAIL, None)

    return redirect(url_for(".user_profile"))


@main.route("/user-profile/mobile-number", methods=["GET", "POST"])
@main.route(
    "/user-profile/mobile-number/delete",
    methods=["GET"],
    endpoint="user_profile_confirm_delete_mobile_number",
)
@user_is_logged_in
def user_profile_mobile_number():
    user = User.from_id(current_user.id)
    form = ChangeMobileNumberForm(mobile_number=current_user.mobile_number)

    if form.validate_on_submit():
        session[NEW_MOBILE] = form.mobile_number.data
        return redirect(url_for(".user_profile_mobile_number_authenticate"))

    if request.endpoint == "main.user_profile_confirm_delete_mobile_number":
        flash(
            "Are you sure you want to delete your mobile number from Notify?", "delete"
        )

    return render_template(
        "views/user-profile/change.html",
        thing="mobile number",
        form_field=form.mobile_number,
        user_auth=user.auth_type,
    )


@main.route("/user-profile/mobile-number/delete", methods=["POST"])
@user_is_logged_in
def user_profile_mobile_number_delete():
    if current_user.auth_type != AuthType.EMAIL_AUTH:
        abort(403)

    current_user.update(mobile_number=None)

    return redirect(url_for(".user_profile"))


@main.route("/user-profile/mobile-number/authenticate", methods=["GET", "POST"])
@user_is_logged_in
def user_profile_mobile_number_authenticate():

    if NEW_MOBILE not in session:
        return redirect(url_for(".user_profile_mobile_number"))

    session[NEW_MOBILE_PASSWORD_CONFIRMED] = True
    current_user.send_verify_code(to=session[NEW_MOBILE])
    create_mobile_number_change_event(
        user_id=current_user.id,
        updated_by_id=current_user.id,
        original_mobile_number=current_user.mobile_number,
        new_mobile_number=session[NEW_MOBILE],
    )
    return redirect(url_for(".user_profile_mobile_number_confirm"))


@main.route("/user-profile/mobile-number/confirm", methods=["GET", "POST"])
@user_is_logged_in
def user_profile_mobile_number_confirm():
    # Validate verify code for form
    def _check_code(cde):
        return user_api_client.check_verify_code(current_user.id, cde, "sms")

    if NEW_MOBILE_PASSWORD_CONFIRMED not in session:
        return redirect(url_for(".user_profile_mobile_number"))

    form = TwoFactorForm(_check_code)

    if form.validate_on_submit():
        current_user.refresh_session_id()
        mobile_number = session[NEW_MOBILE]
        del session[NEW_MOBILE]
        del session[NEW_MOBILE_PASSWORD_CONFIRMED]
        current_user.update(mobile_number=mobile_number)
        return redirect(url_for(".user_profile"))

    return render_template(
        "views/user-profile/confirm.html",
        form_field=form.sms_code,
        thing="mobile number",
    )


@main.route("/user-profile/password", methods=["GET", "POST"])
@user_is_logged_in
def user_profile_password():
    # Validate password for form
    def _check_password(pwd):
        return user_api_client.verify_password(current_user.id, pwd)

    form = ChangePasswordForm(_check_password)

    if form.validate_on_submit():
        user_api_client.update_password(
            current_user.id, password=form.new_password.data
        )
        return redirect(url_for(".user_profile"))

    return render_template("views/user-profile/change-password.html", form=form)


@main.route("/user-profile/disable-platform-admin-view", methods=["GET", "POST"])
@user_is_logged_in
def user_profile_disable_platform_admin_view():
    if not current_user.platform_admin and not session.get(
        "disable_platform_admin_view"
    ):
        abort(403)

    form = ServiceOnOffSettingForm(
        name="Use platform admin view",
        enabled=not session.get("disable_platform_admin_view"),
        truthy="Yes",
        falsey="No",
    )

    form.enabled.param_extensions = {
        "hint": {"text": "Signing in again clears this setting"}
    }

    if form.validate_on_submit():
        session["disable_platform_admin_view"] = not form.enabled.data
        return redirect(url_for(".user_profile"))

    return render_template(
        "views/user-profile/disable-platform-admin-view.html", form=form
    )


def set_timezone():
    # Cookie is set in dashboard.html on page load
    try:
        timezone = request.cookies.get("timezone", "US/Eastern")
        current_app.logger.debug(hilite(f"User's timezone is {timezone}"))
        serialized_user = current_user.serialize()
        if serialized_user["preferred_timezone"] is not timezone:
            current_user.update(preferred_timezone=timezone)
    except Exception:
        current_app.logger.exception(hilite("Can't get timezone"))
