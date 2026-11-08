# Where real data hides

Before calling a double finished, check each of these in the finished output (the
built page, bundle, deck, video, screenshot), not just the data file.

## In code

- Fixture and seed files, mock API responses, test snapshots
- Inline constants: arrays of points, start dates, thresholds, baselines
- Chart series, tooltip strings, legend labels, axis titles
- Hard-coded dates in a second helper function (the axis didn't move: look for it)
- Code comments ("// copied from the Acme export")
- URL params and routes (`/accounts/48213`), query strings, file names
- Environment files and config that name a customer or tenant

## In copy

- Page titles, headers, breadcrumbs, empty-state text
- Footnotes, captions, "data as of" notes
- Prose numbers ("122 sensors went live March 27") that must change with the data
- Alt text and aria labels

## In images and media

- Text baked into exported frames or screenshots (headers, sidebars, avatars)
- Map tiles and satellite views that show a real location
- Video frames between the ones you checked, and the poster frame
- Image metadata (EXIF location, author fields)

## In what's left behind

- Earlier uploads or deploys of the real version still reachable by link
- Artifact assets, CDN blobs, Figma image fills
- Browser storage in a demo machine
- The mapping file (keep it local, never commit it)

## Checks that catch the rest

- `double.py audit <mapping> <output dir> --terms "..."` for every mapped identifier
- A text search of the output for the real customer name, city and any id you remember
- Side-by-side screenshots of real vs double: same shape at a glance, different identity
