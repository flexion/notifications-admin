from flask import abort, current_app
from werkzeug.utils import cached_property

from app.enums import ServicePermission
from app.models import JSONModel, SortByNameMixin
from app.models.job import ImmediateJobs, PaginatedJobs, PaginatedUploads, ScheduledJobs
from app.models.organization import Organization
from app.models.user import InvitedUsers, User, Users
from app.notify_client.api_key_api_client import api_key_api_client
from app.notify_client.billing_api_client import billing_api_client
from app.notify_client.inbound_number_client import inbound_number_client
from app.notify_client.invite_api_client import invite_api_client
from app.notify_client.job_api_client import job_api_client
from app.notify_client.organizations_api_client import organizations_client
from app.notify_client.service_api_client import service_api_client
from app.notify_client.template_folder_api_client import template_folder_api_client
from app.utils import get_default_sms_sender
from notifications_utils.serialised_model import SerialisedModelCollection


class Service(JSONModel, SortByNameMixin):
    ALLOWED_PROPERTIES = {
        "active",
        "billing_contact_email_addresses",
        "billing_contact_names",
        "billing_reference",
        "consent_to_research",
        "contact_link",
        "count_as_live",
        "email_from",
        "go_live_at",
        "go_live_user",
        "id",
        "inbound_api",
        "message_limit",
        "rate_limit",
        "name",
        "notes",
        "prefix_sms",
        "purchase_order_number",
        ServicePermission.RESEARCH_MODE,
        "service_callback_api",
        "volume_email",
        "volume_sms",
    }

    TEMPLATE_TYPES = (
        "email",
        "sms",
    )

    ALL_PERMISSIONS = TEMPLATE_TYPES + (
        ServicePermission.EDIT_FOLDER_PERMISSIONS,
        ServicePermission.EMAIL_AUTH,
        ServicePermission.INBOUND_SMS,
        ServicePermission.INTERNATIONAL_SMS,
        ServicePermission.UPLOAD_DOCUMENT,
    )

    @classmethod
    def from_id(cls, service_id):
        return cls(service_api_client.get_service(service_id)["data"])

    @property
    def permissions(self):
        return self._dict.get("permissions", self.TEMPLATE_TYPES)

    @property
    def billing_details(self):
        billing_details = [
            self.billing_contact_email_addresses,
            self.billing_contact_names,
            self.billing_reference,
            self.purchase_order_number,
        ]
        if any(billing_details):
            return billing_details
        else:
            return None

    def update(self, **kwargs):
        return service_api_client.update_service(self.id, **kwargs)

    def update_count_as_live(self, count_as_live):
        return service_api_client.update_count_as_live(
            self.id, count_as_live=count_as_live
        )

    def update_status(self, live):
        return service_api_client.update_status(self.id, live=live)

    def switch_permission(self, permission):
        return self.force_permission(
            permission,
            on=not self.has_permission(permission),
        )

    def force_permission(self, permission, on=False):
        permissions, permission = set(self.permissions), {permission}

        return self.update_permissions(
            permissions | permission if on else permissions - permission,
        )

    def update_permissions(self, permissions):
        return self.update(permissions=list(permissions))

    def toggle_research_mode(self):
        self.update(research_mode=not self.research_mode)

    @property
    def trial_mode(self):
        return self._dict["restricted"]

    @property
    def live(self):
        return not self.trial_mode

    def has_permission(self, permission):
        if permission not in self.ALL_PERMISSIONS:
            raise KeyError(f"{permission} is not a service permission")
        return permission in self.permissions

    def get_page_of_jobs(self, page):
        return PaginatedJobs(self.id, page=page)

    def get_page_of_uploads(self, page):
        return PaginatedUploads(self.id, page=page)

    @cached_property
    def has_jobs(self):
        return job_api_client.has_jobs(self.id)

    @cached_property
    def immediate_jobs(self):
        if not self.has_jobs:
            return []
        return ImmediateJobs(self.id)

    @cached_property
    def scheduled_jobs(self):
        if not self.has_jobs:
            return []
        return ScheduledJobs(self.id)

    @cached_property
    def scheduled_job_stats(self):
        if not self.has_jobs:
            return {"count": 0}
        return job_api_client.get_scheduled_job_stats(self.id)

    @cached_property
    def invited_users(self):
        return InvitedUsers(self.id)

    def invite_pending_for(self, email_address):
        return email_address.lower() in (
            invited_user.email_address.lower() for invited_user in self.invited_users
        )

    @cached_property
    def active_users(self):
        return Users(self.id)

    @cached_property
    def team_members(self):
        return sorted(
            self.invited_users + self.active_users,
            key=lambda user: user.email_address.lower(),
        )

    @cached_property
    def has_team_members(self):
        return (
            len(
                [
                    user
                    for user in self.team_members
                    if user.has_permission_for_service(
                        self.id, ServicePermission.MANAGE_SERVICE
                    )
                ]
            )
            > 1
        )

    def cancel_invite(self, invited_user_id):
        if str(invited_user_id) not in {user.id for user in self.invited_users}:
            abort(404)

        return invite_api_client.cancel_invited_user(
            service_id=self.id,
            invited_user_id=str(invited_user_id),
        )

    def resend_invite(self, invited_user_id):
        if str(invited_user_id) not in {user.id for user in self.invited_users}:
            abort(404)

        return invite_api_client.resend_invite(
            service_id=self.id,
            invited_user_id=str(invited_user_id),
        )

    def get_team_member(self, user_id):
        if str(user_id) not in {user.id for user in self.active_users}:
            abort(404)

        return User.from_id(user_id)

    @cached_property
    def all_templates(self):
        templates = service_api_client.get_service_templates(self.id)["data"]

        return [
            template
            for template in templates
            if template["template_type"] in self.available_template_types
        ]

    @cached_property
    def all_template_ids(self):
        return {template["id"] for template in self.all_templates}

    def get_template(self, template_id, version=None):
        return service_api_client.get_service_template(self.id, template_id, version)[
            "data"
        ]

    def get_template_folder_with_user_permission_or_403(self, folder_id, user):
        template_folder = self.get_template_folder(folder_id)

        if not user.has_template_folder_permission(template_folder):
            abort(403)

        return template_folder

    def get_template_with_user_permission_or_403(self, template_id, user):
        template = self.get_template(template_id)

        self.get_template_folder_with_user_permission_or_403(template["folder"], user)

        return template

    @property
    def available_template_types(self):
        return list(filter(self.has_permission, self.TEMPLATE_TYPES))

    @property
    def has_templates(self):
        return bool(self.all_templates)

    def has_folders(self):
        return bool(self.all_template_folders)

    @property
    def has_multiple_template_types(self):
        return len({template["template_type"] for template in self.all_templates}) > 1

    @property
    def has_estimated_usage(self):
        return self.consent_to_research is not None and any(
            (
                self.volume_email,
                self.volume_sms,
            )
        )

    def has_templates_of_type(self, template_type):
        return any(
            template
            for template in self.all_templates
            if template["template_type"] == template_type
        )

    @property
    def has_email_templates(self):
        return self.has_templates_of_type("email")

    @property
    def has_sms_templates(self):
        return self.has_templates_of_type("sms")

    @property
    def intending_to_send_email(self):
        if self.volume_email is None:
            return self.has_email_templates
        return self.volume_email > 0

    @property
    def intending_to_send_sms(self):
        if self.volume_sms is None:
            return self.has_sms_templates
        return self.volume_sms > 0

    @cached_property
    def email_reply_to_addresses(self):
        return service_api_client.get_reply_to_email_addresses(self.id)

    @property
    def has_email_reply_to_address(self):
        return bool(self.email_reply_to_addresses)

    @property
    def count_email_reply_to_addresses(self):
        return len(self.email_reply_to_addresses)

    @property
    def default_email_reply_to_address(self):
        return next(
            (
                x["email_address"]
                for x in self.email_reply_to_addresses
                if x["is_default"]
            ),
            None,
        )

    def get_email_reply_to_address(self, id):
        return service_api_client.get_reply_to_email_address(self.id, id)

    @property
    def needs_to_add_email_reply_to_address(self):
        return self.intending_to_send_email and not self.has_email_reply_to_address

    @property
    def shouldnt_use_govuk_as_sms_sender(self):
        return self.organization_type != Organization.TYPE_FEDERAL

    @cached_property
    def sms_senders(self):
        return service_api_client.get_sms_senders(self.id)

    @property
    def sms_senders_with_hints(self):
        def attach_hint(sender):
            hints = []
            if sender["is_default"]:
                hints += ["default"]
            if sender["inbound_number_id"]:
                hints += ["receives replies"]
            if hints:
                sender["hint"] = "(" + " and ".join(hints) + ")"
            return sender

        return [attach_hint(sender) for sender in self.sms_senders]

    @property
    def default_sms_sender(self):
        return get_default_sms_sender(self.sms_senders)

    @property
    def count_sms_senders(self):
        return len(self.sms_senders)

    @property
    def sms_sender_is_govuk(self):
        return self.default_sms_sender in {"GOVUK", "None"}

    def get_sms_sender(self, id):
        return service_api_client.get_sms_sender(self.id, id)

    @property
    def needs_to_change_sms_sender(self):
        return all(
            (
                self.intending_to_send_sms,
                self.shouldnt_use_govuk_as_sms_sender,
                self.sms_sender_is_govuk,
            )
        )

    @property
    def volumes(self):
        return sum(
            filter(
                None,
                (
                    self.volume_email,
                    self.volume_sms,
                ),
            )
        )

    @cached_property
    def free_sms_fragment_limit(self):
        return billing_api_client.get_free_sms_fragment_limit_for_year(self.id) or 0

    @cached_property
    def data_retention(self):
        return service_api_client.get_service_data_retention(self.id)

    def get_data_retention_item(self, id):
        return next((dr for dr in self.data_retention if dr["id"] == id), None)

    def get_days_of_retention(self, notification_type, number_of_days):
        return next(
            (
                dr
                for dr in self.data_retention
                if dr["notification_type"] == notification_type
            ),
            {},
        ).get(
            "days_of_retention",
            current_app.config["ACTIVITY_STATS_LIMIT_DAYS"].get(number_of_days),
        )

    @cached_property
    def organization(self):
        return Organization.from_id(self.organization_id)

    @property
    def organization_id(self):
        return self._dict["organization"]

    @property
    def organization_type(self):
        return self.organization.organization_type or self._dict["organization_type"]

    @property
    def organization_name(self):
        if not self.organization_id:
            return None
        return organizations_client.get_organization_name(self.organization_id)

    @property
    def organization_type_label(self):
        return Organization.TYPE_LABELS.get(self.organization_type)

    @cached_property
    def inbound_number(self):
        return inbound_number_client.get_inbound_sms_number_for_service(self.id)[
            "data"
        ].get("number", "")

    @property
    def has_inbound_number(self):
        return bool(self.inbound_number)

    @cached_property
    def inbound_sms_summary(self):
        if not self.has_permission(ServicePermission.INBOUND_SMS):
            return None
        return service_api_client.get_inbound_sms_summary(self.id)

    @cached_property
    def all_template_folders(self):
        return sorted(
            template_folder_api_client.get_template_folders(self.id),
            key=lambda folder: folder["name"].lower(),
        )

    @cached_property
    def all_template_folder_ids(self):
        return {folder["id"] for folder in self.all_template_folders}

    def get_template_folder(self, folder_id):
        if folder_id is None:
            return {
                "id": None,
                "name": "Templates",
                "parent_id": None,
            }
        return self._get_by_id(self.all_template_folders, folder_id)

    def get_template_folder_path(self, template_folder_id):
        folder = self.get_template_folder(template_folder_id)

        if folder["id"] is None:
            return [folder]

        return self.get_template_folder_path(folder["parent_id"]) + [
            self.get_template_folder(folder["id"])
        ]

    def get_template_path(self, template):
        return self.get_template_folder_path(template["folder"]) + [
            template,
        ]

    @property
    def count_of_templates_and_folders(self):
        return len(self.all_templates + self.all_template_folders)

    def move_to_folder(self, ids_to_move, move_to):
        ids_to_move = set(ids_to_move)

        template_folder_api_client.move_to_folder(
            service_id=self.id,
            folder_id=move_to,
            template_ids=ids_to_move & self.all_template_ids,
            folder_ids=ids_to_move & self.all_template_folder_ids,
        )

    @cached_property
    def api_keys(self):
        return sorted(
            api_key_api_client.get_api_keys(self.id)["apiKeys"],
            key=lambda key: key["name"].lower(),
        )

    def get_api_key(self, id):
        return self._get_by_id(self.api_keys, id)


class Services(SerialisedModelCollection):
    model = Service
