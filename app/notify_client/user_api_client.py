from flask import current_app

from app.notify_client import NotifyAdminAPIClient, cache
from app.utils import hilite
from app.utils.user_permissions import translate_permissions_from_ui_to_db
from notifications_python_client.errors import HTTPError

ALLOWED_ATTRIBUTES = {
    "name",
    "email_address",
    "mobile_number",
    "auth_type",
    "updated_by",
    "current_session_id",
    "email_access_validated_at",
    "preferred_timezone",
}


class UserApiClient(NotifyAdminAPIClient):
    def init_app(self, app):
        super().init_app(app)
        self.admin_url = app.config["ADMIN_BASE_URL"]

    def register_user(self, name, email_address, mobile_number, password, auth_type):
        data = {
            "name": name,
            "email_address": email_address,
            "mobile_number": mobile_number,
            "password": password,
            "auth_type": auth_type,
        }
        user_data = self.post("/user", data)
        return user_data["data"]

    def get_user(self, user_id):
        return self._get_user(user_id)["data"]

    @cache.set("user-{user_id}")
    def _get_user(self, user_id):
        return self.get("/user/{}".format(user_id))

    def get_user_by_email(self, email_address):
        current_app.logger.info(f"Going to get user by email {email_address}")
        user_data = self.post("/user/email", data={"email": email_address})
        return user_data["data"]

    def get_user_by_uuid_or_email(self, user_uuid, email_address):

        user_data = self.post(
            "/user/get-login-gov-user",
            data={"login_uuid": user_uuid, "email": email_address},
        )
        if user_data is None or user_data.get("data") is None:
            return None
        return user_data["data"]

    def get_user_by_email_or_none(self, email_address):
        try:
            return self.get_user_by_email(email_address)
        except HTTPError as e:
            if e.status_code == 404:
                return None
            raise e

    @cache.delete("user-{user_id}")
    def update_user_attribute(self, user_id, **kwargs):
        data = dict(kwargs)
        disallowed_attributes = set(data.keys()) - ALLOWED_ATTRIBUTES
        if disallowed_attributes:
            raise TypeError(
                "Not allowed to update user attributes: {}".format(
                    ", ".join(disallowed_attributes)
                )
            )

        url = "/user/{}".format(user_id)
        user_data = self.post(url, data=data)
        return user_data["data"]

    @cache.delete("user-{user_id}")
    def archive_user(self, user_id):
        return self.post("/user/{}/archive".format(user_id), data=None)

    @cache.delete("user-{user_id}")
    def reset_failed_login_count(self, user_id):
        url = "/user/{}/reset-failed-login-count".format(user_id)
        user_data = self.post(url, data={})
        return user_data["data"]

    @cache.delete("user-{user_id}")
    def update_password(self, user_id, password):
        data = {"_password": password}
        url = "/user/{}/update-password".format(user_id)
        user_data = self.post(url, data=data)
        return user_data["data"]

    @cache.delete("user-{user_id}")
    def verify_password(self, user_id, password):
        try:
            current_app.logger.warn(f"Checking password for {user_id}")
            url = "/user/{}/verify/password".format(user_id)
            data = {"password": password}
            self.post(url, data=data)
            return True
        except HTTPError as e:
            if e.status_code == 400 or e.status_code == 404:
                current_app.logger.error(f"Password for {user_id} was invalid")
                return False
            raise

    def send_verify_code(self, user_id, code_type, to, next_string=None):

        data = {"to": to}
        if next_string:
            data["next"] = next_string
        if code_type == "email":
            data["email_auth_link_host"] = self.admin_url
        endpoint = f"/user/{user_id}/{code_type}-code"
        current_app.logger.warn(hilite(f"Sending verify_code {code_type} to {user_id}"))
        self.post(endpoint, data=data)

    def send_verify_email(self, user_id, to):
        data = {
            "to": to,
            "admin_base_url": self.admin_url,
        }
        endpoint = "/user/{0}/email-verification".format(user_id)
        self.post(endpoint, data=data)

    def send_already_registered_email(self, user_id, to):
        data = {"email": to}
        endpoint = "/user/{0}/email-already-registered".format(user_id)
        self.post(endpoint, data=data)

    @cache.delete("user-{user_id}")
    def check_verify_code(self, user_id, code, code_type):
        data = {"code_type": code_type, "code": code}
        endpoint = "/user/{}/verify/code".format(user_id)
        try:
            current_app.logger.warn(f"Checking verify code for {user_id}")
            self.post(endpoint, data=data)
            return True, ""
        except HTTPError as e:
            if e.status_code == 400 or e.status_code == 404:
                current_app.logger.error(f"Verify code for {user_id} was invalid")
                return False, e.message
            raise

    def get_users_for_service(self, service_id):
        endpoint = "/service/{}/users".format(service_id)
        return self.get(endpoint)["data"]

    def get_users_for_organization(self, org_id):
        endpoint = "/organizations/{}/users".format(org_id)
        return self.get(endpoint)["data"]

    def get_all_users(self):
        endpoint = "/user"
        return self.get(endpoint)["data"]

    def get_all_users_detailed(self):
        endpoint = "/user/report-all-users"
        return self.get(endpoint)["data"]

    @cache.delete("service-{service_id}")
    @cache.delete("service-{service_id}-template-folders")
    @cache.delete("user-{user_id}")
    def add_user_to_service(self, service_id, user_id, permissions, folder_permissions):
        # permissions passed in are the combined UI permissions, not DB permissions
        endpoint = f"/service/{service_id}/users/{user_id}"
        data = {
            "permissions": [
                {"permission": x}
                for x in translate_permissions_from_ui_to_db(permissions)
            ],
            "folder_permissions": folder_permissions,
        }

        self.post(endpoint, data=data)

    @cache.delete("user-{user_id}")
    def add_user_to_organization(self, org_id, user_id):
        resp = self.post("/organizations/{}/users/{}".format(org_id, user_id), data={})
        return resp["data"]

    @cache.delete("service-{service_id}-template-folders")
    @cache.delete("user-{user_id}")
    def set_user_permissions(
        self, user_id, service_id, permissions, folder_permissions=None
    ):
        # permissions passed in are the combined UI permissions, not DB permissions
        data = {
            "permissions": [
                {"permission": x}
                for x in translate_permissions_from_ui_to_db(permissions)
            ],
        }

        if folder_permissions is not None:
            data["folder_permissions"] = folder_permissions

        endpoint = "/user/{}/service/{}/permission".format(user_id, service_id)
        self.post(endpoint, data=data)

    def send_reset_password_url(self, email_address, next_string=None):
        endpoint = "/user/reset-password"
        data = {
            "email": email_address,
            "admin_base_url": self.admin_url,
        }
        if next_string:
            data["next"] = next_string
        self.post(endpoint, data=data)

    def find_users_by_full_or_partial_email(self, email_address):
        endpoint = "/user/find-users-by-email"
        data = {"email": email_address}
        users = self.post(endpoint, data=data)
        return users

    @cache.delete("user-{user_id}")
    def activate_user(self, user_id):
        return self.post("/user/{}/activate".format(user_id), data=None)

    @cache.delete("user-{user_id}")
    def deactivate_user(self, user_id):
        return self.post("/user/{}/deactivate".format(user_id), data=None)

    def send_change_email_verification(self, user_id, new_email):
        endpoint = "/user/{}/change-email-verification".format(user_id)
        data = {"email": new_email}
        self.post(endpoint, data)

    def get_organizations_and_services_for_user(self, user_id):
        endpoint = "/user/{}/organizations-and-services".format(user_id)
        return self.get(endpoint)


user_api_client = UserApiClient()
