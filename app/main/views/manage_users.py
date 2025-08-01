from flask import abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user

from app import current_service, service_api_client
from app.enums import ServicePermission
from app.event_handlers import (
    create_cancel_user_invite_to_service_event,
    create_email_change_event,
    create_invite_user_to_service_event,
    create_mobile_number_change_event,
    create_remove_user_from_service_event,
    create_resend_user_invite_to_service_event,
)
from app.formatters import redact_mobile_number
from app.main import main
from app.main.forms import (
    ChangeEmailForm,
    ChangeMobileNumberForm,
    ChangeNonGovEmailForm,
    InviteUserForm,
    PermissionsForm,
    SearchUsersForm,
)
from app.models.user import InvitedUser, User
from app.utils.user import is_gov_user, user_has_permissions
from app.utils.user_permissions import permission_options
from notifications_python_client.errors import HTTPError


@main.route("/services/<uuid:service_id>/users")
@user_has_permissions(allow_org_user=True)
def manage_users(service_id):
    return render_template(
        "views/manage-users.html",
        users=current_service.team_members,
        current_user=current_user,
        show_search_box=(len(current_service.team_members) > 7),
        form=SearchUsersForm(),
        permissions=permission_options,
    )


@main.route("/services/<uuid:service_id>/users/invite", methods=["GET", "POST"])
@main.route(
    "/services/<uuid:service_id>/users/invite/<uuid:user_id>", methods=["GET", "POST"]
)
@user_has_permissions(ServicePermission.MANAGE_SERVICE)
def invite_user(service_id, user_id=None):
    form_class = InviteUserForm
    form = form_class(
        inviter_email_address=current_user.email_address,
        all_template_folders=current_service.all_template_folders,
        folder_permissions=[],
    )

    if user_id:
        user_to_invite = User.from_id(user_id)
        if user_to_invite.belongs_to_service(current_service.id):
            return render_template(
                "views/user-already-team-member.html",
                user_to_invite=user_to_invite,
            )
        if current_service.invite_pending_for(user_to_invite.email_address):
            return render_template(
                "views/user-already-invited.html",
                user_to_invite=user_to_invite,
            )
        if not user_to_invite.default_organization:
            abort(403)
        if user_to_invite.default_organization.id != current_service.organization_id:
            abort(403)
        form.email_address.data = user_to_invite.email_address
    else:
        user_to_invite = None

    service_has_email_auth = current_service.has_permission(
        ServicePermission.EMAIL_AUTH
    )
    if not service_has_email_auth:
        form.login_authentication.data = "sms_auth"

    if form.validate_on_submit():
        if not form.permissions or len(form.permissions) == 0:
            return render_template(
                "views/user-has-no-permissions.html",
                user_to_invite=user_to_invite,
            )
        email_address = form.email_address.data
        invited_user = InvitedUser.create(
            current_user.id,
            service_id,
            email_address,
            form.permissions,
            form.login_authentication.data,
            form.folder_permissions.data,
        )
        create_invite_user_to_service_event(
            email_address=email_address,
            invited_by_id=current_user.id,
            service_id=service_id,
            ui_permissions=form.permissions,
        )

        flash(
            "Invite sent to {}".format(invited_user.email_address), "default_with_tick"
        )
        return redirect(url_for(".manage_users", service_id=service_id))

    return render_template(
        "views/invite-user.html",
        form=form,
        service_has_email_auth=service_has_email_auth,
        mobile_number=True,
        user_to_invite=user_to_invite,
    )


@main.route("/services/<uuid:service_id>/users/<uuid:user_id>", methods=["GET", "POST"])
@user_has_permissions(ServicePermission.MANAGE_SERVICE)
def edit_user_permissions(service_id, user_id):
    service_has_email_auth = current_service.has_permission(
        ServicePermission.EMAIL_AUTH
    )
    user = current_service.get_team_member(user_id)

    mobile_number = None
    if user.mobile_number:
        mobile_number = redact_mobile_number(user.mobile_number, " ")

    form_class = PermissionsForm

    form = form_class.from_user(
        user,
        service_id,
        folder_permissions=(
            None
            if user.platform_admin
            else [
                f["id"]
                for f in current_service.all_template_folders
                if user.has_template_folder_permission(f)
            ]
        ),
        all_template_folders=(
            None if user.platform_admin else current_service.all_template_folders
        ),
    )

    if form.validate_on_submit():
        user.set_permissions(
            service_id,
            permissions=form.permissions,
            folder_permissions=form.folder_permissions.data,
            set_by_id=current_user.id,
        )
        # Only change the auth type if this is supported for a service.
        if service_has_email_auth:
            user.update(auth_type=form.login_authentication.data)
        return redirect(url_for(".manage_users", service_id=service_id))

    return render_template(
        "views/edit-user-permissions.html",
        user=user,
        form=form,
        service_has_email_auth=service_has_email_auth,
        mobile_number=mobile_number,
        delete=request.args.get("delete"),
    )


@main.route("/services/<uuid:service_id>/users/<uuid:user_id>/delete", methods=["POST"])
@user_has_permissions(ServicePermission.MANAGE_SERVICE)
def remove_user_from_service(service_id, user_id):
    try:
        service_api_client.remove_user_from_service(service_id, user_id)
    except HTTPError as e:
        msg = "You cannot remove the only user for a service"
        if e.status_code == 400 and msg in e.message:
            flash(msg, "info")
            return redirect(url_for(".manage_users", service_id=service_id))
        else:
            abort(500, e)
    else:
        create_remove_user_from_service_event(
            user_id=user_id, removed_by_id=current_user.id, service_id=service_id
        )

    return redirect(url_for(".manage_users", service_id=service_id))


@main.route(
    "/services/<uuid:service_id>/users/<uuid:user_id>/edit-email",
    methods=["GET", "POST"],
)
@user_has_permissions(ServicePermission.MANAGE_SERVICE)
def edit_user_email(service_id, user_id):
    user = current_service.get_team_member(user_id)
    user_email = user.email_address
    session_key = "team_member_email_change-{}".format(user_id)

    if is_gov_user(user_email):
        form = ChangeEmailForm(User.already_registered, email_address=user_email)
    else:
        form = ChangeNonGovEmailForm(User.already_registered, email_address=user_email)

    if request.form.get("email_address", "").strip() == user_email:
        return redirect(url_for(".manage_users", service_id=current_service.id))

    if form.validate_on_submit():
        session[session_key] = form.email_address.data

        return redirect(
            url_for(".confirm_edit_user_email", user_id=user.id, service_id=service_id)
        )

    return render_template(
        "views/manage-users/edit-user-email.html",
        user=user,
        form=form,
        service_id=service_id,
    )


@main.route(
    "/services/<uuid:service_id>/users/<uuid:user_id>/edit-email/confirm",
    methods=["GET", "POST"],
)
@user_has_permissions(ServicePermission.MANAGE_SERVICE)
def confirm_edit_user_email(service_id, user_id):
    user = current_service.get_team_member(user_id)
    session_key = "team_member_email_change-{}".format(user_id)
    if session_key in session:
        new_email = session[session_key]
    else:
        return redirect(
            url_for(".edit_user_email", service_id=service_id, user_id=user_id)
        )
    if request.method == "POST":
        try:
            user.update(email_address=new_email, updated_by=current_user.id)
        except HTTPError as e:
            abort(500, e)
        else:
            create_email_change_event(
                user_id=user.id,
                updated_by_id=current_user.id,
                original_email_address=user.email_address,
                new_email_address=new_email,
            )
        finally:
            session.pop(session_key, None)

        return redirect(url_for(".manage_users", service_id=service_id))
    return render_template(
        "views/manage-users/confirm-edit-user-email.html",
        user=user,
        service_id=service_id,
        new_email=new_email,
    )


@main.route(
    "/services/<uuid:service_id>/users/<uuid:user_id>/edit-mobile-number",
    methods=["GET", "POST"],
)
@user_has_permissions(ServicePermission.MANAGE_SERVICE)
def edit_user_mobile_number(service_id, user_id):
    user = current_service.get_team_member(user_id)
    user_mobile_number = redact_mobile_number(user.mobile_number)

    form = ChangeMobileNumberForm(mobile_number=user_mobile_number)
    if form.mobile_number.data == user_mobile_number and request.method == "POST":
        return redirect(url_for(".manage_users", service_id=service_id))
    if form.validate_on_submit():
        session["team_member_mobile_change"] = form.mobile_number.data

        return redirect(
            url_for(
                ".confirm_edit_user_mobile_number",
                user_id=user.id,
                service_id=service_id,
            )
        )
    return render_template(
        "views/manage-users/edit-user-mobile.html",
        user=user,
        form=form,
        service_id=service_id,
    )


@main.route(
    "/services/<uuid:service_id>/users/<uuid:user_id>/edit-mobile-number/confirm",
    methods=["GET", "POST"],
)
@user_has_permissions(ServicePermission.MANAGE_SERVICE)
def confirm_edit_user_mobile_number(service_id, user_id):
    user = current_service.get_team_member(user_id)
    if "team_member_mobile_change" in session:
        new_number = session["team_member_mobile_change"]
    else:
        return redirect(
            url_for(".edit_user_mobile_number", service_id=service_id, user_id=user_id)
        )
    if request.method == "POST":
        try:
            user.update(mobile_number=new_number, updated_by=current_user.id)
        except HTTPError as e:
            abort(500, e)
        else:
            create_mobile_number_change_event(
                user_id=user.id,
                updated_by_id=current_user.id,
                original_mobile_number=user.mobile_number,
                new_mobile_number=new_number,
            )
        finally:
            session.pop("team_member_mobile_change", None)

        return redirect(url_for(".manage_users", service_id=service_id))

    return render_template(
        "views/manage-users/confirm-edit-user-mobile-number.html",
        user=user,
        service_id=service_id,
        new_mobile_number=new_number,
    )


@main.route(
    "/services/<uuid:service_id>/cancel-invited-user/<uuid:invited_user_id>",
    methods=["GET"],
)
@user_has_permissions(ServicePermission.MANAGE_SERVICE)
def cancel_invited_user(service_id, invited_user_id):
    current_service.cancel_invite(invited_user_id)

    invited_user = InvitedUser.by_id_and_service_id(service_id, invited_user_id)
    create_cancel_user_invite_to_service_event(
        email_address=invited_user.email_address,
        canceled_by_id=current_user.id,
        service_id=service_id,
    )

    flash(f"Invitation cancelled for {invited_user.email_address}", "default_with_tick")
    return redirect(url_for("main.manage_users", service_id=service_id))


@main.route(
    "/services/<uuid:service_id>/resend-invite/<uuid:invited_user_id>",
    methods=["GET"],
)
@user_has_permissions(ServicePermission.MANAGE_SERVICE)
def resend_invite(service_id, invited_user_id):
    current_service.resend_invite(invited_user_id)

    invited_user = InvitedUser.by_id_and_service_id(service_id, invited_user_id)
    create_resend_user_invite_to_service_event(
        email_address=invited_user.email_address,
        resent_by_id=current_user.id,
        service_id=service_id,
    )

    flash(f"Invitation resent for {invited_user.email_address}", "default_with_tick")
    return redirect(url_for("main.manage_users", service_id=service_id))
