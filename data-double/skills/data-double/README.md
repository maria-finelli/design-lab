# Data Double

**A stunt double for production data.** It steps in for the difficult scenes so the
real thing doesn't have to.

## Why I built this

Your prototype isn't really being tested if your data is always on its best behavior.

Conveniently short labels. Just enough rows to fill a table. Charts that always look
beautiful.

Real product data is rarely that cooperative.

What happens when one value dwarfs everything else? When a customer has 10x the
records you expected? When information is missing, inconsistent, or just plain weird?

I've been building prototypes directly against our product codebase, and I want to
catch these problems while I'm designing. Not after something ships.

But there's a tension here: I want to test against the reality of our data without
compromising the privacy of the people behind it.

So I built Data Double.

Think of it as a stunt double for production data. It steps in for the difficult
scenes so the real thing doesn't have to.

It's designed to preserve the shape of the original data: its uneven distributions,
outliers, missing values, and differences in scale. So the prototype encounters the
same kinds of challenges it would with real data, without reproducing the actual
customer records.

**The goal here is to recreate the conditions that challenge the design.**

Because protecting customer data shouldn't mean sacrificing the integrity of how we
test. I'm open-sourcing it so other designers and developers can bring that same
thinking into their workflows.

## What it does

You hand Data Double your real data, and it hands back a slightly different mirror
image. It keeps the **shape** (uneven distributions, outliers, missing values, label
lengths, differences in scale, list sizes, weekday patterns) and drops the
**identity** (names, companies, places, emails, phones, ids, exact dates and values).
Your prototype meets the same challenges it would with real data, without
reproducing anyone's records.

It ships as a [Claude Code](https://claude.com/claude-code) skill with a standalone
Python script you can also run on its own. Standard library only, no installs.

## Before and after

| Field         | Real                                         | Double                                       |
| ------------- | -------------------------------------------- | -------------------------------------------- |
| account_id    | ACC-70806                                    | MDE-34365                                    |
| company       | Westbrook Unified School District Facilities | Ashby Dunmore Westerly Wexford Underhill Co. |
| contact_name  | Ravi Subramanian                             | Florian Brady-Ng                             |
| email         | ravi@westbrook.io                            | bli@orchard.test                             |
| phone         | (392) 552-3862                               | (518) 555-0196                               |
| seats         | 4180 (about 300x the median)                 | 3681 (still about 300x the median)           |
| monthly_spend | $75,811.26                                   | $71,844.80                                   |
| signup_date   | 2026-07-06, a Monday                         | 2026-04-13, still a Monday                   |

(The "real" data in this repo is invented too. See [examples/](../../examples/).)

## Install the skill

```bash
git clone https://github.com/maria-finelli/design-lab.git
cp -r design-lab/data-double/skills/data-double ~/.claude/skills/
```

Then in Claude Code, ask for it in your own words: "make a data double of
`exports/accounts.csv`", "I want to test this table with realistic data", "is this
prototype safe to share?" The skill also works in other agents that read `SKILL.md`
skills.

## Or run the script directly

```bash
python3 scripts/double.py mirror accounts.csv
python3 scripts/double.py mirror accounts.csv orders.json   # related files stay consistent
```

`mirror` guesses what every field is, makes the double, compares the shape with the
original and checks for leaks:

```
shape check (real vs double):
  27 fields, the shape held

leak check:
clean: none of 349 real identifiers appear in 2 file(s)
```

It writes three files next to the input:

| File                    | What it is                                                                         |
| ----------------------- | ---------------------------------------------------------------------------------- |
| `accounts.double.csv`   | the double, same format and structure                                              |
| `accounts.spec.json`    | what it decided each field is; fix a wrong guess and run `mirror` again            |
| `accounts.mapping.json` | real to double. **Re-identifies everything: keep it local.** It's in `.gitignore`. |

Other commands:

```bash
double.py scan    data.json                         # field shapes and a starter spec
double.py make    data.json spec.json               # the double, from your own spec
double.py compare data.json data.double.json        # shape drift, field by field
double.py audit   data.mapping.json dist/           # any real identifier left in a built site?
double.py grow    data.double.json spec.json --times 10   # a heavy dataset
double.py grow    data.double.json spec.json --rows 0     # the empty state
```

Reads JSON (flat or nested: `contact.email`, `items[].price`) and CSV, TSV or PSV.
Spec format: [references/spec.md](references/spec.md).

## How it keeps the shape

- **One scale factor for every number**, then a little jitter per value. Ratios hold, so
  outliers stay outliers and a threshold that was exceeded stays exceeded. Zeros stay
  zero. Formats (`$1,234.50`, `12%`, `N/A`) stay.
- **Whole-week date shifts.** Weekday and weekend patterns hold. All dates in one record
  move together, so durations hold.
- **Length-matched names.** A 4-character company stays short and a 77-character one
  still breaks your table cell.
- **Consistent stand-ins.** The same real id, name or email always maps to the same
  double, across fields and files, so joins work and the person named in a note is the
  same person named in the contact field.
- **Structure untouched.** Record counts, list lengths, missing values, categories and
  statuses are kept exactly.
- **A shape check after every run.** `compare` flags any field whose missing rate,
  spread, label length or list sizes drifted.

## Privacy by design

- `scan`, `profile` and `mirror` never print raw values. Text shows as a mask
  (`Aaaaa Aaaa 99`), so you (or an AI assistant running the tool) can judge each field
  without reading the data. The skill tells Claude not to open the raw file.
- Everything runs locally. Nothing is uploaded.
- Fake emails use reserved domains (`example.com`, `.test`, `.example`) and US phones
  use the fictional 555-01xx range, so nothing reaches a real person.

## Limits

Data Double lowers the risk of sharing realistic data. It is not a formal
anonymization method (it doesn't provide k-anonymity or differential privacy), and it
is not a compliance tool. Specifically:

- **Values are close to real by design.** That's the point for testing, and it means a
  one-of-a-kind outlier (the only 4,000-seat customer) can still be recognized by
  someone who knows it exists. Drop or coarsen anything that identifies on its own.
- **Combinations can identify.** A small town plus a rare job title plus an age can
  point to one person even when the name is gone.
- **It only replaces what it's told about.** Names that appear only in free text need
  to be listed as `terms`. Numbers in prose need a manual edit.
- **The mapping file reverses everything.** Treat it like the original data.

Follow your organization's data policy. When in doubt about regulated data (health,
financial, children's data), ask whoever owns it before it leaves its system.

## Repo layout

```
skills/data-double/
  SKILL.md                         the skill: when to use it and the workflow
  README.md                        this page, so the folder explains itself when shared alone
  scripts/double.py                the tool (Python 3.8+, standard library only)
  references/spec.md               spec format and field kinds
  references/where-data-hides.md   a checklist for finished prototypes, decks and videos
  references/worked-example.md     the example below, step by step
examples/
  accounts.csv, orders.json        invented, deliberately messy "production" data
  *.double.*                       their doubles
  data-double.spec.json            the spec mirror produced for them
```

## License

MIT. See [LICENSE](../../LICENSE).
