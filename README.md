# Sigenergy Schedule — Home Assistant integration

Edit your Sigenergy **time-of-use schedule** from Home Assistant.

Sign in with your mySigen account, and the integration loads your current schedule
and exposes each period's numeric settings as editable `number` entities.

> Scope: this edits the **values** on existing periods. It deliberately does not
> create, delete, or re-time periods — do that in the mySigen app.

## Why cloud and not Modbus

The TOU schedule lives in the cloud EMS. Local Modbus-TCP exposes mode selection and
instantaneous power/SoC control, but not the schedule editor, so schedule changes have
to go through the cloud API.

## Install

**HACS** → Custom repositories → add this repo as an *Integration* → install →
restart Home Assistant → *Settings → Devices & Services → Add Integration →
"Sigenergy Schedule"*.

**Manual**: copy `custom_components/sigen_schedule/` into your HA `config/custom_components/`
and restart.

## Setup

Email, password, and region.

> **Australia and New Zealand accounts must pick "Australia & New Zealand", not
> "Asia Pacific".** They are different servers (`api-aus` vs `api-apac`) and the
> wrong one fails with a plain "authentication failed". This trips up other Sigen
> libraries, which assume ANZ lives on the APAC shard.

## Entities

Per period, one `sensor` showing the window (e.g. `Charging 11:00-14:00`) with the
full raw period in its attributes, plus `number` entities for the values that apply
to that window type:

| Window type | Editable values |
|---|---|
| Charging | Max charge power (grid→battery), Max battery charge power, Max grid import power, Grid charging cut-off SOC |
| Discharging | Max discharge power (battery→grid), Max battery discharge power, Max grid export power, Grid discharging cut-off SOC |
| Self-consumption | Max battery charge/discharge power, Max grid import/export power |

A number showing **unknown** means the field is unset in the API — the system default
applies. Setting a value overrides it. Clearing back to system default isn't supported
yet; do that in the app.

## How writes work

The API has no partial update: `POST /device/dischargesetting/batch/save` replaces the
entire schedule. So changing one number re-posts every period.

To keep that safe the integration:

- serialises writes behind a lock, so concurrent edits can't clobber each other
- validates before sending — periods must tile the whole day (`00:00` → `24:00`, no
  gaps or overlaps, max 24 periods) and refuses to write if they don't
- applies the new value optimistically, then re-reads to reconcile

If someone restructures the schedule in the app, entities for periods that no longer
exist go unavailable rather than writing to the wrong window. Reload the integration
to pick up the new layout.

## Rate limits

The Sigenergy cloud throttles to roughly one request per endpoint per 5 minutes, so
the integration polls every 5 minutes. Edits are applied immediately regardless of the
poll cycle.

## Caveats

This uses undocumented endpoints recovered from the mySigen app (v4.0.0). An app or
firmware update can change them without notice. It writes settings to grid-connected
energy hardware — sanity-check values before automating against them.
