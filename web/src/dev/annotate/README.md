# Dev annotate page

`web/annotate.html` confirms corpus truth (plan section 8.2) and runs the pin drill (plan section 9,
item 4). It is a development tool: the build makes it, and `web/scripts/compose-site.mjs` leaves it
and its `annotate-*` entry files out of the Pages artifact, so the public site never serves it
(`web/src/compose-site.test.ts` checks this).

## Use it on a computer

From `web/`, after a build:

```bash
npm run preview
```

Open `http://localhost:4173/annotate.html`. `npm run dev` serves it at the same path.

## Use it on a phone for one session

The phone and the computer must be on the same home network.

1. From `web/`, build, then serve the build to the network:

   ```bash
   npm run build
   npm run preview -- --host
   ```

   Vite prints a `Network:` address, for example `http://192.168.1.20:4173/`.
2. On the phone, open that address followed by `annotate.html`.
3. When the session ends, stop the server with Ctrl+C. Nothing keeps serving after that.

`--host` makes the preview server listen on every network interface, so any device on the network can
open the site while it runs: serve it only on a network you trust, and only for the session. The
page's own files come from the server, and the photos and annotations you open stay on the phone:
the page never uploads them, and its saved files go where the phone's browser saves files.

The preview address is plain http, which is not a secure context, so the page hashes photos with its
own SHA-256 (`sha256.ts`) rather than `crypto.subtle`.

## Verify a photo

1. Open the photo, then its annotation from `corpus/annotations/` (optional). Coordinates are source
   image pixels (the annotation's `canvas`), so a downsized copy from `corpus/images/` works; a photo
   whose shape differs from the canvas by more than 1 percent is refused, because it was rotated.
2. The pins start from the verified claim, else proposer A's, else proposer B's; "Start from" picks
   another.
3. Frame the quilt one of two ways: the outer edge with border bands set inward (tick "The field
   corners show" to pin those too), or the field corners of a quilt with no border.
4. Set each band by selecting it and dragging a handle on its inner line, with the steppers (a quarter
   square each), or by typing inches once the finished square size is set.
5. Set the counts as blocks x squares per block on each axis, or with "Count from one square".
6. Choose the construction class and save. The file keeps every claim it had and adds or replaces the
   `verified-jake` claims for the frame, the counts and the class; copy it over
   `corpus/annotations/<stem>.json` (or the private folder for a private photo).

## Pin drill

"Start the pin drill" hides the loaded annotation: pins start at a neutral inset with one square and
no bands. Each pin placement (the end of a drag, or an arrow-key nudge) and each counts change is a
record with its time from the start; the last counts record is the final entry. "Save drill records"
writes `<stem>.drill.json` with the photo's path, sha256 and canvas, the frame mode and the device's
viewport, pixel ratio and pointer type. D10 scores the records against verified truth.
