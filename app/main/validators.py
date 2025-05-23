import re
from abc import ABC, abstractmethod

from wtforms import ValidationError

from app.main._commonly_used_passwords import commonly_used_passwords
from app.models.spreadsheet import Spreadsheet
from app.utils.user import is_gov_user
from notifications_utils.field import Field
from notifications_utils.formatters import formatted_list
from notifications_utils.recipients import InvalidEmailError, validate_email_address
from notifications_utils.sanitise_text import SanitiseSMS


class CommonlyUsedPassword:
    def __init__(self, message=None):
        if not message:
            message = "Password is in list of commonly used passwords."
        self.message = message

    def __call__(self, form, field):
        if field.data in commonly_used_passwords:
            raise ValidationError(self.message)


class CsvFileValidator:
    def __init__(self, message="Not a csv file"):
        self.message = message

    def __call__(self, form, field):
        if not Spreadsheet.can_handle(field.data.filename):
            raise ValidationError(
                "{} is not a spreadsheet that Notify can read".format(
                    field.data.filename
                )
            )


class ValidGovEmail:
    def __call__(self, form, field):
        if field.data == "":
            return

        message = "Enter a public sector email address."

        if not is_gov_user(field.data.lower()):
            raise ValidationError(message)


class ValidEmail:
    message = "Enter a valid email address"

    def __call__(self, form, field):
        if not field.data:
            return

        try:
            validate_email_address(field.data)
        except InvalidEmailError:
            raise ValidationError(self.message)


class NoCommasInPlaceHolders:
    def __init__(self, message="You cannot put commas between double parenthesis"):
        self.message = message

    def __call__(self, form, field):
        if "," in "".join(Field(field.data).placeholders):
            raise ValidationError(self.message)


class NoElementInSVG(ABC):
    @property
    @abstractmethod
    def element(self):
        pass

    @property
    @abstractmethod
    def message(self):
        pass

    def __call__(self, form, field):
        svg_contents = field.data.stream.read().decode("utf-8")
        field.data.stream.seek(0)
        if f"<{self.element}" in svg_contents.lower():
            raise ValidationError(self.message)


class NoEmbeddedImagesInSVG(NoElementInSVG):
    element = "image"
    message = "This SVG has an embedded raster image in it and will not render well"


class NoTextInSVG(NoElementInSVG):
    element = "text"
    message = "This SVG has text which has not been converted to paths and may not render well"


class OnlySMSCharacters:
    def __init__(self, *args, template_type, **kwargs):
        self._template_type = template_type
        super().__init__(*args, **kwargs)

    def __call__(self, form, field):
        non_sms_characters = sorted(
            list(SanitiseSMS.get_non_compatible_characters(field.data))
        )
        if non_sms_characters:
            raise ValidationError(
                "Please remove the unaccepted character {} in your message, then save again".format(
                    formatted_list(
                        non_sms_characters,
                        conjunction="and",
                        before_each="",
                        after_each="",
                    ),
                )
            )


class LettersNumbersSingleQuotesFullStopsAndUnderscoresOnly:
    regex = re.compile(r"^[a-zA-Z0-9\s\._']+$")

    def __init__(self, message="Use letters and numbers only"):
        self.message = message

    def __call__(self, form, field):
        if field.data and not re.match(self.regex, field.data):
            raise ValidationError(self.message)


class DoesNotStartWithDoubleZero:
    def __init__(self, message="Cannot start with 00"):
        self.message = message

    def __call__(self, form, field):
        if field.data and field.data.startswith("00"):
            raise ValidationError(self.message)


class FieldCannotContainComma:
    def __init__(self, message="Cannot contain a comma"):
        self.message = message

    def __call__(self, form, field):
        if field.data and "," in field.data:
            raise ValidationError(self.message)


class MustContainAlphanumericCharacters:
    regex = re.compile(r".*[a-zA-Z0-9].*[a-zA-Z0-9].*")

    def __init__(self, message="Must include at least two alphanumeric characters"):
        self.message = message

    def __call__(self, form, field):
        if field.data and not re.match(self.regex, field.data):
            raise ValidationError(self.message)
