"""Schema for broker registry entries.

Each broker is one YAML file in ``registry/brokers/``. Entries hold public
metadata only and must never contain anyone's personal data. The schema is
strict (unknown keys are errors), so a typo can't silently disable a field.
"""

from __future__ import annotations

import datetime as dt
import string
from enum import StrEnum
from typing import Annotated, Self

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

Slug = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")]


class Category(StrEnum):
    PEOPLE_SEARCH = "people_search"
    BACKGROUND_CHECK = "background_check"
    MARKETING = "marketing"
    RISK = "risk"
    UPSTREAM = "upstream"


class SearchMethod(StrEnum):
    HTTP = "http"
    BROWSER = "browser"
    MANUAL = "manual"


class OptOutMethod(StrEnum):
    WEB_FORM = "web_form"
    EMAIL = "email"
    ACCOUNT = "account"
    PHONE = "phone"
    MAIL = "mail"


class Verification(StrEnum):
    NONE = "none"
    EMAIL_LINK = "email_link"
    PHONE_CODE = "phone_code"
    ID_DOCUMENT = "id_document"


class RequestField(StrEnum):
    """Data a broker may ask for. ``requires`` is a ceiling: drivers send nothing else."""

    LISTING_URL = "listing_url"
    FULL_NAME = "full_name"
    FIRST = "first"
    LAST = "last"
    CITY = "city"
    STATE = "state"
    ZIP = "zip"
    ADDRESS = "address"
    EMAIL = "email"  # always the opt-out alias, never a personal address
    PHONE = "phone"
    DOB = "dob"
    AGE = "age"


# Placeholders a search URL template may use. Kept deliberately small (query hygiene).
SEARCH_INPUTS = frozenset({"first", "last", "middle", "city", "state"})

_Strict = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class Search(BaseModel):
    model_config = _Strict

    method: SearchMethod
    url: AnyHttpUrl | None = None
    url_template: str | None = None
    inputs: tuple[str, ...] = ()
    result_selector: str | None = None
    rate_limit_per_min: int = Field(default=6, ge=1, le=60)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.method is not SearchMethod.MANUAL and not self.url_template:
            raise ValueError("automated search needs url_template")
        if self.url_template:
            names = {n for _, n, _, _ in string.Formatter().parse(self.url_template) if n}
            if bad := names - SEARCH_INPUTS:
                raise ValueError(f"url_template uses unsupported inputs: {sorted(bad)}")
            if names != set(self.inputs):
                raise ValueError("inputs must list exactly the url_template placeholders")
        return self


class OptOut(BaseModel):
    model_config = _Strict

    method: OptOutMethod
    url: AnyHttpUrl | None = None
    email: str | None = Field(default=None, pattern=r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$")
    phone: str | None = None
    alternatives: tuple[OptOutMethod, ...] = ()
    requires: tuple[RequestField, ...] = ()
    verification: tuple[Verification, ...] = (Verification.NONE,)
    captcha: bool = False
    processing_days: int | None = Field(default=None, ge=0, le=365)
    notes: str = ""

    @model_validator(mode="after")
    def _check(self) -> Self:
        needs = {
            OptOutMethod.WEB_FORM: self.url,
            OptOutMethod.ACCOUNT: self.url,
            OptOutMethod.EMAIL: self.email,
            OptOutMethod.PHONE: self.phone,
        }
        if self.method in needs and not needs[self.method]:
            raise ValueError(f"opt-out method {self.method} needs its url/email/phone")
        return self

    @property
    def mode(self) -> str:
        """How hands-free this opt-out can be.

        ``auto``: MRclean can complete it unattended (email, no human check).
        ``assisted``: MRclean pre-fills; you submit and click the confirmation.
        ``manual``: a CAPTCHA, phone code, ID or phone/mail method needs you.
        """
        human = {Verification.ID_DOCUMENT, Verification.PHONE_CODE}
        if self.captcha or human & set(self.verification):
            return "manual"
        if self.method is OptOutMethod.EMAIL:
            return "auto"
        if self.method in {OptOutMethod.WEB_FORM, OptOutMethod.ACCOUNT}:
            return "assisted"
        return "manual"


class Relisting(BaseModel):
    model_config = _Strict

    rescan_days: int = Field(default=90, ge=7, le=730)


class Broker(BaseModel):
    """One data broker, as described in ``registry/brokers/<id>.yaml``."""

    model_config = _Strict

    id: Slug
    name: str = Field(min_length=2)
    url: AnyHttpUrl
    category: Category
    priority: int = Field(ge=1, le=3, description="1 = highest exposure, do first")
    parent: Slug | None = None
    covers: tuple[str, ...] = Field(default=(), description="sites removed by this opt-out")
    search: Search
    optout: OptOut
    relisting: Relisting = Relisting()
    sources: tuple[AnyHttpUrl, ...] = Field(min_length=1)
    last_verified: dt.date
    verified_live: bool = Field(
        default=False,
        description="True once the opt-out was walked on the live site, not just read",
    )

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.parent == self.id:
            raise ValueError("a broker can't be its own parent")
        if self.last_verified > dt.date.today():
            raise ValueError("last_verified is in the future")
        return self

    def is_stale(self, today: dt.date | None = None, max_age_days: int = 180) -> bool:
        return ((today or dt.date.today()) - self.last_verified).days > max_age_days
