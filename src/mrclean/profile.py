"""The identity profile: who to look for, kept only in the encrypted store.

Query hygiene lives here too. :meth:`Profile.search_variants` produces the
narrow queries scanners may send: name variant x state, and nothing else.
Everything richer (age, phones, emails, past streets) is used only locally,
to score results.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mrclean.store import Store

_Model = ConfigDict(extra="forbid", str_strip_whitespace=True)

USState = Annotated[str, Field(pattern=r"^[A-Z]{2}$")]


class NameKind(StrEnum):
    CURRENT = "current"
    FORMER = "former"  # maiden name, previous legal name
    ALIAS = "alias"  # nickname or common misspelling brokers use


class Name(BaseModel):
    model_config = _Model

    first: str = Field(min_length=1)
    middle: str = ""
    last: str = Field(min_length=1)
    kind: NameKind = NameKind.CURRENT

    @property
    def full(self) -> str:
        return " ".join(p for p in (self.first, self.middle, self.last) if p)


class Address(BaseModel):
    model_config = _Model

    street: str = ""
    city: str = Field(min_length=1)
    state: USState
    zip: str = Field(default="", pattern=r"^(\d{5}(-\d{4})?)?$")
    current: bool = False


class SearchQuery(BaseModel):
    """One outbound search. Only these fields may ever be sent to a broker."""

    model_config = ConfigDict(frozen=True)

    first: str
    last: str
    middle: str = ""
    state: USState
    city: str = ""


class Profile(BaseModel):
    model_config = _Model

    names: list[Name] = []
    addresses: list[Address] = []
    phones: list[str] = []
    emails: list[str] = []
    usernames: list[str] = []
    birth_year: int | None = Field(default=None, ge=1900, le=2100)

    @model_validator(mode="after")
    def _dedupe(self) -> Self:
        for attr in ("phones", "emails", "usernames"):
            setattr(self, attr, list(dict.fromkeys(getattr(self, attr))))
        return self

    def identifiers(self) -> list[str]:
        """Every literal that must never appear in logs or commits."""
        out = [n.full for n in self.names] + [f"{n.first} {n.last}" for n in self.names]
        out += [a.street for a in self.addresses if a.street]
        out += self.phones + self.emails + self.usernames
        return list(dict.fromkeys(v for v in out if v))

    def search_variants(self, *, with_city: bool = False) -> list[SearchQuery]:
        """Fan out narrow queries: each name variant x each state lived in.

        A middle name adds a second variant with just the initial, because
        brokers index both. ``with_city`` adds city (used only when a common
        name returns too many results to page through).
        """
        places = {(a.state, a.city if with_city else "") for a in self.addresses}
        variants: dict[SearchQuery, None] = {}
        for name in self.names:
            middles = [""] + ([name.middle[0]] if name.middle else [])
            for state, city in sorted(places):
                for middle in middles:
                    q = SearchQuery(
                        first=name.first, last=name.last, middle=middle, state=state, city=city
                    )
                    variants[q] = None
        return list(variants)


def load_profile(store: Store) -> Profile:
    row = store.conn.execute("SELECT data FROM profile WHERE id = 1").fetchone()
    return Profile.model_validate_json(row[0]) if row else Profile()


def save_profile(store: Store, profile: Profile) -> None:
    with store.transaction() as conn:
        conn.execute(
            "INSERT INTO profile (id, data) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET data = excluded.data, "
            "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')",
            (json.dumps(profile.model_dump(mode="json")),),
        )
