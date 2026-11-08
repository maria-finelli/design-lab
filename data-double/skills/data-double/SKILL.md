---
name: data-double
description: 'Make a data double: a stunt double for real production data that keeps its shape (uneven distributions, outliers, missing values, long and short labels, differences in scale, list sizes, weekday patterns) and drops its identity (names, companies, places, emails, phones, ids, exact dates and values). Hand it the real data and it hands back a slightly different mirror image to design and test against. Use it whenever someone wants to prototype or test with realistic data without exposing customers, build fixtures or seed data from a production export or API response, share a prototype, demo, screenshot, video, deck or case study that was built on real data, or asks to anonymize, scrub, sanitize, mask or fake data that still behaves like the real thing. Also use it when someone says data double, stunt double, "is this safe to share", "can I use real data", "make realistic test data" or wants empty, typical and heavy datasets for a design, even if they never say "data double".'
---

# Data Double

A data double is a stunt double for production data. It steps in for the difficult
scenes so the real thing doesn't have to.

A prototype is only tested if its data misbehaves the way real data does: the label
that's three times longer than the mockup, the customer with 10x the records, the one
value that dwarfs the rest of the chart, the gaps, the "N/A" in a number column. Pretty,
rounded, evenly spaced sample data hides all of that. A data double keeps it.

Two rules, and everything below serves them:

1. **Keep the shape.** Record counts, list lengths, missing values, outliers, the ratio
   of every value to every other, label lengths, durations, weekday patterns, the order
   of events. The prototype should hit the same problems it would hit with real data.
2. **Lose the identity.** Nobody should be able to tell which customer, person or place
   it came from, even someone who knows the real data well.

## The fast path: mirror

Given a real file (JSON, CSV, TSV or PSV), run:

```bash
python3 <skill-dir>/scripts/double.py mirror data.json
python3 <skill-dir>/scripts/double.py mirror accounts.csv orders.json   # related files, one consistent double
```

`mirror` guesses what every field is, makes the double, compares its shape with the
real data and checks the double for leaks. It writes:

- `data.double.json`: the double, same format and structure as the input
- `data.spec.json`: what it decided each field is (edit and rerun to correct it)
- `data.mapping.json`: real to double. **This re-identifies everything.** It stays on
  the user's machine: never commit, upload, paste or share it.

Pass related files together. The same customer then gets the same stand-in everywhere,
so ids still join and names still match across files.

## Keep the real data out of the conversation

The tool is built so the real values never need to pass through the chat. Follow it:

- Don't `cat`, `head` or Read the raw file. Use `scan`, `profile` and `mirror`, which
  print field shapes and masked examples (`Aaaaa Aaaa 99`), never raw text.
- Read the double, not the original, when you need to see actual rows.
- Don't open or print the mapping file.
- If the user pastes real records into the chat, say once that a file on disk keeps
  them out of the transcript, then carry on with what they gave you.

## Workflow

1. **Find every place the data lives.** Fixtures and JSON, CSV exports, API responses,
   inline JS constants, chart series, tooltips, footnotes, page titles, URL params,
   file names, image text, alt text, code comments. Data hides in prose too ("122
   accounts went live on March 27"). See [references/where-data-hides.md](references/where-data-hides.md).
2. **Mirror the structured data.** Run `mirror` on every file in one call. Read the
   field list it prints and check every guess before trusting the result:
   - A numeric id guessed as `number` gets scaled. Set it to `id`.
   - A category guessed as `label` (or a name left as `keep`) is the common miss.
     Customer-specific names (projects, sites, products named after a client) are
     identity, not categories.
   - Percentages, ratings and other bounded values need `"scale": 1` and a `min`/`max`.
   - Free text gets kind `text`. Names that only appear inside text (not in a field
     of their own) go in the spec's `terms`.
     Edit the spec and rerun until the field list is right. The full spec format is in
     [references/spec.md](references/spec.md).
3. **Check the shape.** `mirror` prints any field that drifted (missing rate, spread,
   label length, list sizes). "The shape held" is the goal. Investigate any drift.
4. **Code and pages: change the source, then rebuild.** When the data is constants in
   code, replace them with the doubled values (or point the code at the doubled file)
   and let the page compute totals, averages and headlines. Never hand-edit a derived
   number. After changing a start date, check the rendered axis: a second hard-coded
   date is common.
5. **Images and video: re-render from the doubled source.** If text is baked into an
   image, repaint it in the same face, weight and width, on every state it appears in.
6. **Audit the finished output**, not just the data file:
   ```bash
   python3 <skill-dir>/scripts/double.py audit data.mapping.json dist/ --terms "Real Customer Name"
   ```
   Audit only knows what's in the mapping. Also read the prose, captions, URLs and
   images yourself, and compare screenshots of real vs double: the shape should match
   at a glance.
7. **Clean up.** Delete uploads, deploys and blobs that still hold the real data once
   the double replaces them. Keep the mapping local or delete it.
8. **Report.** Give the user a short real-to-double table, one row per kind of data
   (names, ids, dates, values), plus anything left as it was and why.

## What changes and what stays

| Data                              | What the double does                                                                                                                                                              |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| People, companies, places, labels | Fictional stand-ins of about the same length and word count, so truncation and wrapping behave the same                                                                           |
| Emails                            | Same pattern (`first.last@`, `jsmith@`), reserved domains (`example.com`, `.test`, `.example`); one real domain maps to one fake domain                                           |
| Phones                            | Same format; US numbers go to the fictional 555-01xx range                                                                                                                        |
| Ids, serials, SKUs, UUIDs         | New values in the same format and length; the same real id always maps to the same double, so joins still work                                                                    |
| Unit labels (6F, 12B)             | Floors and letters permuted, so the set keeps its floors, letters and count                                                                                                       |
| Dates                             | The whole set shifts by whole weeks (weekdays and weekends hold), each record moves a few hours more, all its dates together (durations hold)                                     |
| Numbers                           | One scale factor for the whole dataset (0.85 to 0.95 or 1.05 to 1.15), then a little jitter per value. Outliers stay outliers, zeros stay zero, formats (`$1,234.50`, `12%`) stay |
| Missing values and markers        | Kept exactly, including `N/A`, `null`, empty strings                                                                                                                              |
| Categories, statuses, booleans    | Kept: they're structure, not identity                                                                                                                                             |
| Record counts and list lengths    | Kept exactly                                                                                                                                                                      |

A one-day shift or a 1% nudge is a disguise, not a double. Anyone who knows the real
data still recognizes it. Move far enough that the real calendar and the real numbers
don't line up, and change at least two of name, date and value for anything that names
a place or person.

## Three sizes

Test a screen against three datasets, as engineers do:

- **Empty:** a new account, no records (`grow --rows 0`).
- **Typical:** a median case. Double a real one.
- **Heavy:** the extreme: the most records, the longest names, the densest week. Double
  the real worst case if one exists. If not, `grow --times 10` resamples the double
  with fresh ids and jittered values and dates, so the clusters and overlaps that make
  heavy data hard survive. Say when a heavy set was grown rather than real.

```bash
python3 <skill-dir>/scripts/double.py grow data.double.json data.spec.json --times 10
python3 <skill-dir>/scripts/double.py grow data.double.json data.spec.json --rows 0
```

## The other commands

```bash
double.py scan    data.json [--write spec.json]  # field shapes and a starter spec, nothing written
double.py make    data.json spec.json            # the double, from a spec you wrote
double.py profile data.json                      # the shape of one dataset
double.py compare data.json data.double.json     # shape drift, field by field
```

## Don'ts

- Don't label the UI "sample data" or "demo". The prototype has to read as real; say
  it's a double in the README, caption or hand-off instead.
- Don't thin it out, round it or space events evenly.
- Don't keep a real name because it's "probably fine".
- Don't put the mapping, the raw export or a real id in a commit, an artifact, a
  public link or a chat.
- Don't promise more than it does. A double lowers the risk of sharing; it is not a
  formal anonymization guarantee. Tiny datasets and one-of-a-kind outliers can still
  be recognizable to someone who knows them (see the README's limits section).

A worked example is in [references/worked-example.md](references/worked-example.md).
