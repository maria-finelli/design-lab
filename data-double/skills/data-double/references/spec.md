# Spec reference

A spec is a JSON file that says what each field is. `mirror` and `scan --write` make a
starter one; edit it and rerun.

```json
{
  "seed": 48213,
  "scale": 0.92,
  "shift_weeks": -6,
  "jitter": 0.08,
  "record_jitter_hours": 12,
  "text_units": false,
  "terms": { "Northwind Clinic": "org", "Dr. Ana Ruiz": "person" },
  "fields": {
    "account_id": "id",
    "company": "org",
    "contact.name": "person",
    "contact.email": "email",
    "signup_date": "date",
    "seats": "number",
    "uptime_pct": {
      "kind": "number",
      "scale": 1,
      "jitter": 0.01,
      "min": 0,
      "max": 100
    },
    "items[].sku": "id",
    "readings[]": "number",
    "notes": "text",
    "internal_flag": "drop"
  }
}
```

## Settings

| Key                   | Default                              | What it does                                                                                            |
| --------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| `seed`                | random, printed                      | Same seed + same data = same double. Pin it so rebuilds stay stable.                                    |
| `scale`               | random, 0.85 to 0.95 or 1.05 to 1.15 | One factor for every number, so ratios between fields hold.                                             |
| `shift_weeks`         | random, 3 to 12 weeks either way     | Whole weeks keep weekday and weekend patterns.                                                          |
| `jitter`              | 0.08                                 | Each number moves up to 8% more, on top of the scale.                                                   |
| `record_jitter_hours` | 12                                   | Each record's dates move together by up to this many hours, so durations hold.                          |
| `text_units`          | false                                | Also replace unit labels (6F, 12B) inside free text. Off by default because "10AM" looks like a unit.   |
| `terms`               | none                                 | Real strings that aren't a field of their own, with a kind. Replaced in free text and checked by audit. |
| `grow_jitter_hours`   | 48                                   | How far `grow` moves each copied record's dates.                                                        |

## Field names

- A flat column: `"seats"`
- Nested object: `"contact.email"`
- A field of each object in a list: `"items[].price"`
- A list of plain values: `"readings[]"` (or just `"readings"`)

Fields not named in the spec are kept as they are. `scan` lists every field, so check
that nothing identifying was left out.

## Kinds

| Kind     | For                                                          | Result                                                                                             |
| -------- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| `person` | people's names                                               | fictional name, similar length and word count                                                      |
| `org`    | companies, customers, vendors                                | fictional organization, similar length                                                             |
| `place`  | addresses, sites, buildings, stores                          | fictional place, keeps a leading street number                                                     |
| `label`  | project, product or campaign names that identify a customer  | fictional words, similar length                                                                    |
| `email`  | emails                                                       | same pattern, reserved domain, one real domain to one fake                                         |
| `phone`  | phone numbers                                                | same format, 555-01xx for US numbers                                                               |
| `id`     | ids, account numbers, SKUs, zips                             | new value, same format (letters stay letters, digits digits)                                       |
| `uuid`   | UUIDs                                                        | new UUID                                                                                           |
| `hex`    | `0x...` serials                                              | new hex, same length                                                                               |
| `unit`   | apartment, room, seat labels like 6F                         | floor and letter permuted                                                                          |
| `date`   | ISO dates, epoch seconds or ms, `03/07/2026`, `Mar 07, 2026` | shifted, same format                                                                               |
| `number` | quantities, money, durations                                 | scaled and jittered, same format (`$1,234.50`, `12%`)                                              |
| `text`   | free text, notes, descriptions                               | every value mapped elsewhere, plus emails, phones, UUIDs and hex serials found inside it, replaced |
| `keep`   | categories, statuses, booleans                               | unchanged                                                                                          |
| `drop`   | fields nobody needs                                          | removed from the double                                                                            |

An object instead of a kind string sets per-field options: `{"kind": "number", "scale": 1,
"jitter": 0.02, "min": 0, "max": 100}`. Use it for percentages, ratings, scores, or any
number with a hard limit, and for a field that must stay in step with another field
(give both the same `scale`).

## Things the tool can't see

- Names that only appear in free text and nowhere in a field: add them to `terms`.
- Numbers in prose ("122 accounts"): edit by hand, consistent with the doubled data.
- Values that identify by combination (a tiny town + a rare job title + an age): drop
  or coarsen one of them.
