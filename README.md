# Kensington Elementary AAPAC website

Source for kensingtonaapac.org, the site of the African American Parent Advisory Council at Kensington Elementary School (West Contra Costa Unified). Hosted on GitHub Pages from this repository. Contact: hello@kensingtonaapac.org

## Files

- index.html: the whole site, one page.
- photos/: Ruby Bridges Walk photos by Ittai Shiu, at 480, 800 and 1600 pixels wide, in WebP and JPG.
- fonts/: Young Serif, Source Serif 4 and Figtree (SIL Open Font License), served from this site.
- calendar.ics: the AAPAC calendar people subscribe to (Google, Apple, Outlook). Add or change an event here and subscribers get it on their own.
- aapac-meetings-2026-27.ics, kcsd-board-2026-12-10.ics: older single files, kept so earlier links still work.
- privacy.html: privacy and accessibility page, linked from the footer.
- og-image.png: the preview image shown when the link is shared.
- favicon.ico, favicon.svg, icon-192.png, icon-512.png, apple-touch-icon.png, site.webmanifest: site icons.
- banner.jpg, robots.txt, sitemap.xml, CNAME.

## Weekly update (about ten minutes)

1. In index.html, find the section with id="this-week".
2. Change the eyebrow line ("Week of ...").
3. Add the newest line at the top of "What we did". Keep what is public: no private conversations, no names of families or children.
4. Rewrite "What comes next", each item with its "Why".
5. In "Coming up" and "Dates", add new items. Each dated item carries data-until="YYYY-MM-DD" and hides itself after that day; data-from="YYYY-MM-DD" makes an item appear from that day. "Coming up" shows the next three. "What we did" shows the latest five and folds the rest behind a button on its own.
6. Add any new AAPAC date to calendar.ics too (give it a new UID; keep times in UTC).
7. Change the "Updated" date in the footer and the lastmod date in sitemap.xml.

## Agendas and notes for the four meetings

1. Save the agenda as a PDF named like notes/2026-12-14-agenda.pdf, and the summary as notes/2026-12-14-notes.pdf. Upload both into a notes/ folder in this repository.
2. In index.html, find class="record-list". On that meeting's line, replace the text "Agenda by Dec 7" with a link: <a href="notes/2026-12-14-agenda.pdf">Agenda</a>. Do the same for the notes.
3. Summaries name no families or children, and say what was decided and what happens next.

## Site check

.github/workflows/site-check.yml checks the site every hour: the home page, the calendar file, the HTTPS certificate and the domain registration. If something is wrong it opens an issue here, which GitHub emails to the owner, and it closes the issue when the site is back to normal. Every Monday it also checks the outside links. To run it by hand, open the Actions tab, choose Site check, then Run workflow. It also opens a reminder issue when the "Week of" line on the site is more than eight days old, and closes it after the update. GitHub pauses scheduled checks in a repository with no activity for 60 days; the weekly update keeps it active.
