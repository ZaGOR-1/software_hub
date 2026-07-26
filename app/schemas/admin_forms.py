"""Validated server-rendered administration form payloads."""

from datetime import date
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)
from pydantic import (
    ValidationError as PydanticValidationError,
)

from app.models.enums import Architecture, PackageType, ReleaseChannel, Visibility


class AdminFormModel(BaseModel):
    """Strict base model for browser form payloads."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class CategoryAdminForm(AdminFormModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(default="", max_length=140)
    description: str = Field(default="", max_length=2_000)
    sort_order: int = Field(default=0, ge=0, le=1_000_000)
    is_visible: bool = False


class TagAdminForm(AdminFormModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(default="", max_length=140)


class SoftwareAdminForm(AdminFormModel):
    name: str = Field(min_length=1, max_length=180)
    slug: str = Field(default="", max_length=200)
    short_description: str = Field(min_length=1, max_length=500)
    full_description: str = Field(default="", max_length=20_000)
    developer_name: str = Field(default="", max_length=180)
    official_website_url: str = Field(default="", max_length=2_048)
    source_url: str = Field(default="", max_length=2_048)
    license_name: str = Field(default="", max_length=180)
    category_id: int | None = Field(default=None, ge=1)
    tag_ids: tuple[int, ...] = ()
    supported_os: str = Field(default="", max_length=4_000)
    system_requirements: str = Field(default="", max_length=8_000)
    visibility: Visibility = Visibility.PRIVATE
    is_featured: bool = False

    @field_validator("category_id", mode="before")
    @classmethod
    def empty_category_to_none(cls, value: Any) -> Any:
        return None if value is None or value == "" else value

    @field_validator("tag_ids", mode="before")
    @classmethod
    def normalize_tag_ids(cls, value: Any) -> Any:
        if value is None or value == "":
            return ()
        if isinstance(value, (list, tuple)):
            return tuple(value)
        return (value,)


class ReleaseAdminForm(AdminFormModel):
    version: str = Field(min_length=1, max_length=100)
    release_channel: ReleaseChannel = ReleaseChannel.STABLE
    release_date: date | None = None
    changelog: str = Field(default="", max_length=20_000)

    @field_validator("release_date", mode="before")
    @classmethod
    def empty_date_to_none(cls, value: Any) -> Any:
        return None if value is None or value == "" else value


class ReleaseFileUploadForm(AdminFormModel):
    display_filename: str = Field(default="", max_length=255)
    architecture: Architecture = Architecture.OTHER
    package_type: PackageType = PackageType.OTHER
    platform: str = Field(default="Windows", min_length=1, max_length=100)
    edition: str = Field(default="", max_length=180)
    visibility: Visibility = Visibility.PRIVATE
    source_url: str = Field(default="", max_length=2_048)
    admin_note: str = Field(default="", max_length=4_000)


def validation_messages(exc: PydanticValidationError) -> tuple[str, ...]:
    """Return bounded, value-free form validation feedback."""

    messages: list[str] = []
    for error in exc.errors(include_input=False, include_url=False):
        location = ".".join(str(part) for part in error.get("loc", ()))
        message = str(error.get("msg", "Invalid value."))
        messages.append(f"{location}: {message}" if location else message)
    return tuple(messages[:20])
