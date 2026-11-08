# Worked example: accounts and orders

The repo's `examples/` folder holds two invented "production" files, built to misbehave
the way real data does:

- `accounts.csv`: 30 customer accounts. One has 4,180 seats while the median is about 10. One company name is 77 characters long, another is 4. Some phones are blank, some
  spend values are `N/A`, and the notes mention people and emails by name.
- `orders.json`: 40 orders with nested `ship_to` objects and an `items` list. Most
  orders have 0 to 6 items. One has 80.

## One command

```bash
python3 skills/data-double/scripts/double.py mirror examples/accounts.csv examples/orders.json
```

Both files go in one call, so the same customer gets the same stand-in in both and
every order still points at a real (doubled) account.

```
what each field looks like:
  account_id      id      identifier: format kept, value replaced
  company         org     probably an organization
  contact_name    person  probably a person
  email           email   emails
  phone           phone   phone numbers
  plan            keep    4 repeated values: a category or status, keep it
  seats           number  numbers
  monthly_spend   number  formatted numbers
  signup_date     date    ISO dates
  ...
  items[].sku     id      identifier: format kept, value replaced
  status          keep    3 repeated values: a category or status, keep it

shape check (real vs double):
  27 fields, the shape held

leak check:
clean: none of 349 real identifiers appear in 2 file(s)
```

## Real vs double

The outlier account:

|               | Real                                                    | Double                                                 |
| ------------- | ------------------------------------------------------- | ------------------------------------------------------ |
| account_id    | ACC-70806                                               | MDE-34365                                              |
| company       | Westbrook Unified School District Facilities            | Ashby Dunmore Westerly Wexford Underhill Co.           |
| contact_name  | Ravi Subramanian                                        | Florian Brady-Ng                                       |
| email         | ravi@westbrook.io                                       | bli@orchard.test                                       |
| phone         | (392) 552-3862                                          | (518) 555-0196                                         |
| seats         | 4180                                                    | 3681                                                   |
| monthly_spend | $75,811.26                                              | $71,844.80                                             |
| signup_date   | 2026-07-06 (a Monday)                                   | 2026-04-13 (a Monday)                                  |
| notes         | Renewal owner is Ravi Subramanian, cc ravi@westbrook.io | Renewal owner is Florian Brady-Ng, cc bli@orchard.test |

What held:

- The 4,180-seat account is still roughly 300x the median, so the chart that has to
  cope with it still has to cope with it.
- The 44-character company name is still 44 characters, and the 77-character one is
  still long enough to break a table cell.
- The blank phones and `N/A` spends are blank and `N/A` in the same rows.
- Signup dates still land on weekdays, and each account's signup-to-last-active span
  is within a few hours of the real one.
- The 80-item order still has 80 items. Every other order keeps its item count.
- The name and email inside the notes were swapped for the same stand-ins as their
  own fields.

## Three sizes

```bash
python3 skills/data-double/scripts/double.py grow examples/accounts.double.csv examples/data-double.spec.json --times 10   # 300 accounts, fresh ids
python3 skills/data-double/scripts/double.py grow examples/accounts.double.csv examples/data-double.spec.json --rows 0     # the empty state
```

## A double, not a disguise

The common failure is a light touch: shift dates by a day, nudge values by 1%, keep
the company name because it's "only internal". Anyone who knows the real data still
recognizes it. A double moves the whole calendar by weeks, scales every number by
one factor and replaces every name, and the comparison shows that the shape survived
anyway.
