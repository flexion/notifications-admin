from functools import partial

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from markupsafe import Markup

from app import (
    current_service,
    format_delta,
    nl2br,
    service_api_client,
    template_folder_api_client,
    template_statistics_client,
)
from app.enums import ServicePermission
from app.formatters import character_count, message_count
from app.main import main
from app.main.forms import (
    EmailTemplateForm,
    SearchTemplatesForm,
    SetTemplateSenderForm,
    SMSTemplateForm,
    TemplateAndFoldersSelectionForm,
    TemplateFolderForm,
)
from app.main.views.send import get_sender_details
from app.models.service import Service
from app.models.template_list import TemplateList, TemplateLists
from app.utils import NOTIFICATION_TYPES, should_skip_template_page
from app.utils.templates import get_template
from app.utils.user import user_has_permissions
from notifications_python_client.errors import HTTPError
from notifications_utils import SMS_CHAR_COUNT_LIMIT

form_objects = {
    "email": EmailTemplateForm,
    "sms": SMSTemplateForm,
}


@main.route("/services/<uuid:service_id>/templates/<uuid:template_id>")
@user_has_permissions()
def view_template(service_id, template_id):
    template = current_service.get_template(template_id)
    template_folder = current_service.get_template_folder(template["folder"])

    user_has_template_permission = current_user.has_template_folder_permission(
        template_folder
    )
    if should_skip_template_page(template):
        return redirect(
            url_for(".set_sender", service_id=service_id, template_id=template_id)
        )

    return render_template(
        "views/templates/template.html",
        template=get_template(
            template,
            current_service,
            show_recipient=True,
        ),
        user_has_template_permission=user_has_template_permission,
    )


@main.route("/services/<uuid:service_id>/templates/all", methods=["GET", "POST"])
@main.route("/services/<uuid:service_id>/templates", methods=["GET", "POST"])
@main.route(
    "/services/<uuid:service_id>/templates/folders/<uuid:template_folder_id>",
    methods=["GET", "POST"],
)
@main.route(
    "/services/<uuid:service_id>/templates/<template_type:template_type>",
    methods=["GET", "POST"],
)
@main.route(
    "/services/<uuid:service_id>/templates/all/folders/<uuid:template_folder_id>",
    methods=["GET", "POST"],
)
@main.route(
    "/services/<uuid:service_id>/templates/<template_type:template_type>/folders/<uuid:template_folder_id>",
    methods=["GET", "POST"],
)
@user_has_permissions()
def choose_template(service_id, template_type="all", template_folder_id=None):
    template_folder = current_service.get_template_folder(template_folder_id)

    user_has_template_folder_permission = current_user.has_template_folder_permission(
        template_folder
    )

    template_list = TemplateList(
        current_service, template_type, template_folder_id, current_user
    )

    all_template_folders = [
        item.folder
        for item in TemplateList(service=current_service, user=current_user)
        if item.is_folder
    ]

    templates_and_folders_form = TemplateAndFoldersSelectionForm(
        all_template_folders=all_template_folders,
        template_list=template_list,
        template_type=template_type,
        available_template_types=current_service.available_template_types,
        allow_adding_copy_of_template=(
            current_service.all_templates or len(current_user.service_ids) > 1
        ),
    )
    option_hints = {template_folder_id: "current folder"}

    single_notification_channel = None
    notification_channels = list(
        set(current_service.permissions).intersection(NOTIFICATION_TYPES)
    )
    if len(notification_channels) == 1:
        single_notification_channel = notification_channels[0]

    if request.method == "POST" and templates_and_folders_form.validate_on_submit():
        if not current_user.has_permissions(ServicePermission.MANAGE_TEMPLATES):
            abort(403)
        try:
            return process_folder_management_form(
                templates_and_folders_form, template_folder_id
            )
        except HTTPError as e:
            flash(e.message)
    elif templates_and_folders_form.trying_to_add_unavailable_template_type:
        return redirect(
            url_for(
                ".action_blocked",
                service_id=current_service.id,
                notification_type=templates_and_folders_form.add_template_by_template_type.data,
                return_to="add_new_template",
            )
        )

    if "templates_and_folders" in templates_and_folders_form.errors:
        flash("Select at least one template or folder")

    initial_state = request.args.get("initial_state")
    if request.method == "GET" and initial_state:
        templates_and_folders_form.op = initial_state

    return render_template(
        "views/templates/choose.html",
        current_template_folder_id=template_folder_id,
        template_folder_path=current_service.get_template_folder_path(
            template_folder_id
        ),
        template_list=template_list,
        show_search_box=current_service.count_of_templates_and_folders > 7,
        show_template_nav=(
            current_service.has_multiple_template_types
            and (len(current_service.all_templates) > 2)
        ),
        template_nav_items=get_template_nav_items(template_folder_id),
        template_type=template_type,
        search_form=SearchTemplatesForm(current_service.api_keys),
        templates_and_folders_form=templates_and_folders_form,
        move_to_children=templates_and_folders_form.move_to.children(),
        user_has_template_folder_permission=user_has_template_folder_permission,
        single_notification_channel=single_notification_channel,
        option_hints=option_hints,
    )


def process_folder_management_form(form, current_folder_id):
    current_service.get_template_folder_with_user_permission_or_403(
        current_folder_id, current_user
    )
    new_folder_id = None

    if form.is_add_template_op:
        return _add_template_by_type(
            form.add_template_by_template_type.data,
            current_folder_id,
        )

    if form.is_add_folder_op:
        new_folder_id = template_folder_api_client.create_template_folder(
            current_service.id, name=form.get_folder_name(), parent_id=current_folder_id
        )

    if form.is_move_op:
        # if we've just made a folder, we also want to move there
        move_to_id = new_folder_id or form.move_to.data

        current_service.move_to_folder(
            ids_to_move=form.templates_and_folders.data, move_to=move_to_id
        )

    return redirect(request.url)


def get_template_nav_label(value):
    return {
        "all": "All",
        "sms": "Text message",
        "email": "Email",
    }[value]


def get_template_nav_items(template_folder_id):
    return [
        (
            get_template_nav_label(key),
            key,
            url_for(
                ".choose_template",
                service_id=current_service.id,
                template_type=key,
                template_folder_id=template_folder_id,
            ),
            "",
        )
        for key in ["all"] + current_service.available_template_types
    ]


def _view_template_version(service_id, template_id, version):
    return dict(
        template=get_template(
            current_service.get_template(template_id, version=version), current_service
        )
    )


@main.route(
    "/services/<uuid:service_id>/templates/<uuid:template_id>/version/<int:version>"
)
@user_has_permissions()
def view_template_version(service_id, template_id, version):
    return render_template(
        "views/templates/template_history.html",
        **_view_template_version(
            service_id=service_id, template_id=template_id, version=version
        ),
    )


def _add_template_by_type(template_type, template_folder_id):
    if template_type == "copy-existing":
        return redirect(
            url_for(
                ".choose_template_to_copy",
                service_id=current_service.id,
            )
        )

    return redirect(
        url_for(
            ".add_service_template",
            service_id=current_service.id,
            template_type=template_type,
            template_folder_id=template_folder_id,
        )
    )


@main.route("/services/<uuid:service_id>/templates/copy")
@main.route("/services/<uuid:service_id>/templates/copy/from-folder/<uuid:from_folder>")
@main.route(
    "/services/<uuid:service_id>/templates/copy/from-service/<uuid:from_service>"
)
@main.route(
    "/services/<uuid:service_id>/templates/copy/from-service/<uuid:from_service>/from-folder/<uuid:from_folder>"
)
@user_has_permissions(ServicePermission.MANAGE_TEMPLATES)
def choose_template_to_copy(
    service_id,
    from_service=None,
    from_folder=None,
):
    if from_service:
        current_user.belongs_to_service_or_403(from_service)
        service = Service(service_api_client.get_service(from_service)["data"])

        return render_template(
            "views/templates/copy.html",
            services_templates_and_folders=TemplateList(
                service, template_folder_id=from_folder, user=current_user
            ),
            template_folder_path=service.get_template_folder_path(from_folder),
            from_service=service,
            search_form=SearchTemplatesForm(current_service.api_keys),
        )

    else:
        return render_template(
            "views/templates/copy.html",
            services_templates_and_folders=TemplateLists(current_user),
            search_form=SearchTemplatesForm(current_service.api_keys),
        )


@main.route(
    "/services/<uuid:service_id>/templates/copy/<uuid:template_id>",
    methods=["GET", "POST"],
)
@user_has_permissions(ServicePermission.MANAGE_TEMPLATES)
def copy_template(service_id, template_id):
    from_service = request.args.get("from_service")

    current_user.belongs_to_service_or_403(from_service)

    template = service_api_client.get_service_template(from_service, template_id)[
        "data"
    ]

    template_folder = template_folder_api_client.get_template_folder(
        from_service, template["folder"]
    )
    if not current_user.has_template_folder_permission(template_folder):
        abort(403)

    if request.method == "POST":
        return add_service_template(service_id, template["template_type"])

    template["template_content"] = template["content"]
    template["name"] = _get_template_copy_name(template, current_service.all_templates)
    form = form_objects[template["template_type"]](**template)

    return render_template(
        "views/edit-{}-template.html".format(template["template_type"]),
        form=form,
        template=template,
        heading_action="Add",
        services=current_user.service_ids,
    )


def _get_template_copy_name(template, existing_templates):
    template_names = [existing["name"] for existing in existing_templates]

    for index in reversed(range(1, 10)):
        if "{} (copy {})".format(template["name"], index) in template_names:
            return "{} (copy {})".format(template["name"], index + 1)

    if "{} (copy)".format(template["name"]) in template_names:
        return "{} (copy 2)".format(template["name"])

    return "{} (copy)".format(template["name"])


@main.route(
    (
        "/services/<uuid:service_id>/templates/action-blocked/"
        "<template_type:notification_type>/<return_to>"
    )
)
@main.route(
    (
        "/services/<uuid:service_id>/templates/action-blocked/"
        "<template_type:notification_type>/<return_to>/<uuid:template_id>"
    )
)
@user_has_permissions(ServicePermission.MANAGE_TEMPLATES)
def action_blocked(service_id, notification_type, return_to, template_id=None):
    back_link = {
        "add_new_template": partial(
            url_for, ".choose_template", service_id=current_service.id
        ),
        "templates": partial(
            url_for, ".choose_template", service_id=current_service.id
        ),
        "view_template": partial(
            url_for,
            ".view_template",
            service_id=current_service.id,
            template_id=template_id,
        ),
    }.get(return_to)

    return (
        render_template(
            "views/templates/action_blocked.html",
            service_id=service_id,
            notification_type=notification_type,
            back_link=back_link(),
        ),
        403,
    )


@main.route(
    "/services/<uuid:service_id>/templates/folders/<uuid:template_folder_id>/manage",
    methods=["GET", "POST"],
)
@user_has_permissions(ServicePermission.MANAGE_TEMPLATES)
def manage_template_folder(service_id, template_folder_id):
    template_folder = current_service.get_template_folder_with_user_permission_or_403(
        template_folder_id, current_user
    )
    form = TemplateFolderForm(
        name=template_folder["name"],
        users_with_permission=template_folder.get("users_with_permission", None),
        all_service_users=[
            user for user in current_service.active_users if user.id != current_user.id
        ],
    )
    if form.validate_on_submit():
        if (
            current_user.has_permissions(ServicePermission.MANAGE_SERVICE)
            and form.users_with_permission.all_service_users
        ):
            users_with_permission = form.users_with_permission.data + [current_user.id]
        else:
            users_with_permission = None
        template_folder_api_client.update_template_folder(
            current_service.id,
            template_folder_id,
            name=form.name.data,
            users_with_permission=users_with_permission,
        )
        return redirect(
            url_for(
                ".choose_template",
                service_id=service_id,
                template_folder_id=template_folder_id,
            )
        )

    return render_template(
        "views/templates/manage-template-folder.html",
        form=form,
        template_folder_path=current_service.get_template_folder_path(
            template_folder_id
        ),
        current_service_id=current_service.id,
        template_folder_id=template_folder_id,
        template_type="all",
    )


@main.route(
    "/services/<uuid:service_id>/templates/folders/<uuid:template_folder_id>/delete",
    methods=["GET", "POST"],
)
@user_has_permissions(ServicePermission.MANAGE_TEMPLATES)
def delete_template_folder(service_id, template_folder_id):
    template_folder = current_service.get_template_folder_with_user_permission_or_403(
        template_folder_id, current_user
    )
    template_list = TemplateList(
        service=current_service, template_folder_id=template_folder_id
    )

    if not template_list.folder_is_empty:
        flash("You must empty this folder before you can delete it", "info")
        return redirect(
            url_for(
                ".choose_template",
                service_id=service_id,
                template_type="all",
                template_folder_id=template_folder_id,
            )
        )

    if request.method == "POST":
        try:
            template_folder_api_client.delete_template_folder(
                current_service.id, template_folder_id
            )

            return redirect(
                url_for(
                    ".choose_template",
                    service_id=service_id,
                    template_folder_id=template_folder["parent_id"],
                )
            )
        except HTTPError as e:
            msg = "Folder is not empty"
            if e.status_code == 400 and msg in e.message:
                flash("You must empty this folder before you can delete it", "info")
                return redirect(
                    url_for(
                        ".choose_template",
                        service_id=service_id,
                        template_type="all",
                        template_folder_id=template_folder_id,
                    )
                )
            else:
                abort(500, e)
    else:
        flash(
            "Are you sure you want to delete the ‘{}’ folder?".format(
                template_folder["name"]
            ),
            "delete",
        )
        return manage_template_folder(service_id, template_folder_id)


@main.route(
    "/services/<uuid:service_id>/templates/add-<template_type:template_type>",
    methods=["GET", "POST"],
)
@main.route(
    "/services/<uuid:service_id>/templates/folders/<uuid:template_folder_id>/add-<template_type:template_type>",
    methods=["GET", "POST"],
)
@user_has_permissions(ServicePermission.MANAGE_TEMPLATES)
def add_service_template(service_id, template_type, template_folder_id=None):
    if template_type not in current_service.available_template_types:
        return redirect(
            url_for(
                ".action_blocked",
                service_id=service_id,
                notification_type=template_type,
                template_folder_id=template_folder_id,
                return_to="templates",
            )
        )

    form = form_objects[template_type]()
    if form.validate_on_submit():
        if form.process_type.data == "priority":
            abort_403_if_not_admin_user()
        try:
            new_template = service_api_client.create_service_template(
                form.name.data,
                template_type,
                form.template_content.data,
                service_id,
                form.subject.data if hasattr(form, "subject") else None,
                template_folder_id,
            )
        except HTTPError as e:
            if (
                e.status_code == 400
                and "content" in e.message
                and any(
                    ["character count greater than" in x for x in e.message["content"]]
                )
            ):
                form.template_content.errors.extend(e.message["content"])
            else:
                raise e
        else:
            return redirect(
                url_for(
                    ".view_template",
                    service_id=service_id,
                    template_id=new_template["data"]["id"],
                )
            )

    return render_template(
        "views/edit-{}-template.html".format(template_type),
        form=form,
        template_type=template_type,
        template_folder_id=template_folder_id,
        heading_action="New",
    )


def abort_403_if_not_admin_user():
    if not current_user.platform_admin:
        abort(403)


@main.route(
    "/services/<uuid:service_id>/templates/<uuid:template_id>/edit",
    methods=["GET", "POST"],
)
@user_has_permissions(ServicePermission.MANAGE_TEMPLATES)
def edit_service_template(service_id, template_id):
    template = current_service.get_template_with_user_permission_or_403(
        template_id, current_user
    )
    template["template_content"] = template["content"]
    form = form_objects[template["template_type"]](**template)
    if form.validate_on_submit():
        if form.process_type.data != template["process_type"]:
            abort_403_if_not_admin_user()

        subject = form.subject.data if hasattr(form, "subject") else None

        new_template_data = {
            "name": form.name.data,
            "content": form.template_content.data,
            "subject": subject,
            "template_type": template["template_type"],
            "id": template["id"],
            "process_type": form.process_type.data,
            "reply_to_text": template["reply_to_text"],
        }

        new_template = get_template(new_template_data, current_service)
        template_change = get_template(template, current_service).compare_to(
            new_template
        )

        if (
            template_change.placeholders_added
            and not request.form.get("confirm")
            and current_service.api_keys
        ):
            return render_template(
                "views/templates/breaking-change.html",
                template_change=template_change,
                new_template=new_template,
                form=form,
            )
        try:
            service_api_client.update_service_template(
                template_id,
                form.name.data,
                template["template_type"],
                form.template_content.data,
                service_id,
                subject,
            )
        except HTTPError as e:
            if e.status_code == 400:
                if "content" in e.message and any(
                    ["character count greater than" in x for x in e.message["content"]]
                ):
                    form.template_content.errors.extend(e.message["content"])
                else:
                    raise e
            else:
                raise e
        else:
            return redirect(
                url_for(
                    ".view_template", service_id=service_id, template_id=template_id
                )
            )

    if template["template_type"] not in current_service.available_template_types:
        return redirect(
            url_for(
                ".action_blocked",
                service_id=service_id,
                notification_type=template["template_type"],
                return_to="view_template",
                template_id=template_id,
            )
        )
    else:
        return render_template(
            "views/edit-{}-template.html".format(template["template_type"]),
            form=form,
            template=template,
            heading_action="Edit",
        )


@main.route(
    "/services/<uuid:service_id>/templates/count-<template_type:template_type>-length",
    methods=["POST"],
)
@user_has_permissions()
def count_content_length(service_id, template_type):
    if template_type not in {"sms"}:
        abort(404)

    error, message = _get_content_count_error_and_message_for_template(
        get_template(
            {
                "template_type": template_type,
                "content": request.form.get("template_content", ""),
            },
            current_service,
        )
    )

    return jsonify(
        {
            "html": render_template(
                "partials/templates/content-count-message.html",
                error=error,
                message=message,
            )
        }
    )


def _get_content_count_error_and_message_for_template(template):
    if template.template_type == "sms":
        s1 = (
            "<html><body>Looks like your template may have one of these characters "
            "• ™ ∞ ≤ or ≥ or emoji, which won't save."
        )
        s2 = "<br>Please remove any unaccepted characters or emojis and try again.</body></html>"

        # Define characters that should be blocked
        BLOCKED_CHARACTERS = {"•", "™", "∞", "≤", "≥"}

        def contains_blocked_characters(content):
            """Check if the content contains explicitly blocked characters."""
            return any(c in BLOCKED_CHARACTERS for c in content)

        # Check for blocked characters
        if contains_blocked_characters(template.content):
            warning = f"{s1}{s2}"
            return False, Markup(warning)  # nosec

        # If message is too long, return the length error
        if template.is_message_too_long():
            return True, (
                f"You have "
                f"{character_count(template.content_count_without_prefix - SMS_CHAR_COUNT_LIMIT)} "
                f"too many"
            )

        # Show charge message as usual if no warning
        if template.placeholders:
            return False, Markup(
                f"Will be charged as {message_count(template.fragment_count, template.template_type)} "
                f"(not including personalization)."
            )  # nosec

        return False, Markup(
            f"Will be charged as {message_count(template.fragment_count, template.template_type)}."
        )  # nosec


@main.route(
    "/services/<uuid:service_id>/templates/<uuid:template_id>/delete",
    methods=["GET", "POST"],
)
@user_has_permissions(ServicePermission.MANAGE_TEMPLATES)
def delete_service_template(service_id, template_id):
    template = current_service.get_template_with_user_permission_or_403(
        template_id, current_user
    )

    if request.method == "POST":
        service_api_client.delete_service_template(service_id, template_id)
        return redirect(
            url_for(
                ".choose_template",
                service_id=service_id,
                template_folder_id=template["folder"],
            )
        )

    try:
        last_used_notification = (
            template_statistics_client.get_last_used_date_for_template(
                service_id, template["id"]
            )
        )
        message = (
            "This template has never been used."
            if not last_used_notification
            else "This template was last used {}.".format(
                format_delta(last_used_notification)
            )
        )

    except HTTPError as e:
        if e.status_code == 404:
            message = None
        else:
            raise e

    flash(
        [
            "Are you sure you want to delete ‘{}’?".format(template["name"]),
            message,
            template["name"],
        ],
        "delete",
    )
    return render_template(
        "views/templates/template.html",
        template=get_template(
            template,
            current_service,
            show_recipient=True,
        ),
        user_has_template_permission=True,
    )


@main.route(
    "/services/<uuid:service_id>/templates/<uuid:template_id>/redact", methods=["GET"]
)
@user_has_permissions(ServicePermission.MANAGE_TEMPLATES)
def confirm_redact_template(service_id, template_id):
    template = current_service.get_template_with_user_permission_or_403(
        template_id, current_user
    )

    return render_template(
        "views/templates/template.html",
        template=get_template(
            template,
            current_service,
            show_recipient=True,
        ),
        user_has_template_permission=True,
        show_redaction_message=True,
    )


@main.route(
    "/services/<uuid:service_id>/templates/<uuid:template_id>/redact", methods=["POST"]
)
@user_has_permissions(ServicePermission.MANAGE_TEMPLATES)
def redact_template(service_id, template_id):
    service_api_client.redact_service_template(service_id, template_id)

    flash(
        "Personalized content will be hidden for messages sent with this template",
        "default_with_tick",
    )

    return redirect(
        url_for(
            ".view_template",
            service_id=service_id,
            template_id=template_id,
        )
    )


@main.route("/services/<uuid:service_id>/templates/<uuid:template_id>/versions")
@user_has_permissions(ServicePermission.VIEW_ACTIVITY)
def view_template_versions(service_id, template_id):
    return render_template(
        "views/templates/choose_history.html",
        versions=[
            get_template(
                template,
                current_service,
            )
            for template in service_api_client.get_service_template_versions(
                service_id, template_id
            )["data"]
        ],
    )


@main.route(
    "/services/<uuid:service_id>/templates/<uuid:template_id>/set-template-sender",
    methods=["GET", "POST"],
)
@user_has_permissions(ServicePermission.MANAGE_TEMPLATES)
def set_template_sender(service_id, template_id):
    template = current_service.get_template_with_user_permission_or_403(
        template_id, current_user
    )
    sender_details = get_template_sender_form_dict(service_id, template)
    no_senders = sender_details.get("no_senders", False)

    form = SetTemplateSenderForm(
        sender=sender_details["current_choice"],
        sender_choices=sender_details["value_and_label"],
    )
    form.sender.param_extensions = {"items": []}
    for item_value, _item_label in sender_details["value_and_label"]:
        if item_value == sender_details["default_sender"]:
            extensions = {"hint": {"text": "(Default)"}}
        else:
            extensions = (
                {}
            )  # if no extensions needed, send an empty dict to preserve order of items

        form.sender.param_extensions["items"].append(extensions)

    if form.validate_on_submit():
        service_api_client.update_service_template_sender(
            service_id,
            template_id,
            form.sender.data if form.sender.data else None,
        )
        return redirect(
            url_for(".view_template", service_id=service_id, template_id=template_id)
        )

    return render_template(
        "views/templates/set-template-sender.html",
        form=form,
        template_id=template_id,
        no_senders=no_senders,
    )


def get_template_sender_form_dict(service_id, template):
    context = {
        "email": {"field_name": "email_address"},
        "sms": {"field_name": "sms_sender"},
    }[template["template_type"]]

    sender_format = context["field_name"]
    service_senders = get_sender_details(service_id, template["template_type"])
    context["default_sender"] = next(
        (x["id"] for x in service_senders if x["is_default"]), "Not set"
    )
    if not service_senders:
        context["no_senders"] = True

    context["value_and_label"] = [
        (sender["id"], nl2br(sender[sender_format])) for sender in service_senders
    ]
    context["value_and_label"].insert(
        0, ("", "Blank")
    )  # Add blank option to start of list

    context["current_choice"] = ""
    return context
