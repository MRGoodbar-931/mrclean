# Broker registry

Each broker is one YAML file in `src/mrclean/registry/brokers/`, named by its `id`.
Entries hold **public metadata only**. Never put anyone's personal data in one.
CI validates every file, and so does `mrclean registry validate`.

| Field | Meaning |
| --- | --- |
| `id` | Lowercase slug. Must match the filename. |
| `category` | `people_search`, `background_check`, `marketing`, `risk` or `upstream` |
| `priority` | 1 (do first) to 3 |
| `parent` | The broker whose opt-out should run first (upstream). |
| `covers` | Sites the same opt-out removes you from. |
| `search.method` | `http`, `browser` or `manual`. Automated methods need `url_template`. |
| `search.url_template` | Only `{first}`, `{last}`, `{middle}`, `{city}` and `{state}` are allowed. That's query hygiene, enforced. |
| `optout.method` | `web_form`, `email`, `account`, `phone` or `mail` |
| `optout.requires` | The most this broker will ever be sent. Drivers send nothing else. |
| `optout.verification` | `none`, `email_link`, `phone_code` or `id_document`. MRclean never uploads ID. |
| `optout.captcha` | true makes the opt-out `manual`. MRclean never solves CAPTCHAs. |
| `relisting.rescan_days` | How often to check again after removal (default 90). |
| `sources` | Where these facts came from (at least one). |
| `last_verified` | When the facts were last checked against a source. |
| `verified_live` | true only once someone walked the opt-out on the live site. |

The opt-out **mode** is derived from these fields:

- `auto`: unattended (email, no human check)
- `assisted`: pre-filled, and you submit it
- `manual`: CAPTCHA, phone code, ID, or a phone/mail method
