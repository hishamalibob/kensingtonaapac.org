# Kensington Elementary AAPAC website

Source for kensingtonaapac.org, the site of the African American Parent Advisory Council at Kensington Elementary School (West Contra Costa Unified). Hosted on GitHub Pages from this repository. Contact: hello@kensingtonaapac.org

## Files

- index.html: the whole site, one page.
- photos/: Ruby Bridges Walk photos by Ittai Shiu, at 480, 800 and 1600 pixels wide, in WebP and JPG.
- fonts/: Young Serif, Source Serif 4 and Figtree (SIL Open Font License), served from this site.
- calendar.ics: the AAPAC calendar people subscribe to (Google, Apple, Outlook). Add or change an event here and subscribers get it on their own.
- aapac-meetings-2026-27.ics, kcsd-board-2026-12-10.ics: older single files, kept so earlier links still work.
- privacy.html: privacy and accessibility page, linked from the footer.
- share-2026.jpg: the preview image shown when the link is shared. og-image.png is the earlier one, kept so old shares still show a picture.
- favicon.ico, favicon.svg, icon-192.png, icon-512.png, apple-touch-icon.png, site.webmanifest: site icons.
- robots.txt, sitemap.xml, CNAME.
- .github/: the automatic checks described below. Not part of the published site.

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

## How the site looks after itself

Two automatic checks live in this repository. Neither needs you unless an email arrives.

**Publish guard** (.github/workflows/publish-guard.yml) runs every time files are published. It checks that the page is whole, that every photo, font and file the page uses is there, that the scripts run, that the calendar is valid and that CNAME is in place. If something is broken it waits three minutes, in case more files are still coming, and looks again. If the files are still broken it puts the last working version back and opens an issue that says what was wrong. The undone change stays in the history. To publish something the check wrongly objects to, put [skip-check] in the commit message.

**Site check** (.github/workflows/site-check.yml) looks at the live site from the outside. It is set to run every 15 minutes; GitHub often runs scheduled jobs less often than asked. It checks:

- the home page and every file the page uses
- the three other ways of typing the address (http, and www with and without https), which must all forward to https://kensingtonaapac.org/
- the HTTPS certificate (warns 14 days before it ends) and the domain registration (warns 60 days before)
- the DNS records listed below
- that the live site shows the newest published files

If the site is down, or is not showing the newest files, it asks GitHub to publish the site again and looks once more three minutes later. If a problem remains it opens an issue, which GitHub emails to the owner, and it closes the issue when the site is back to normal. On Mondays it also checks the outside links and keeps its own schedule switched on (GitHub switches off schedules in repositories that go quiet for 60 days). It opens a reminder when the "Week of" line is more than eight days old.

Both use the two scripts in .github/scripts (check.py and guard.sh) and only tools GitHub already provides, so there is nothing outside to keep up to date.

A separate daily check that does not run on GitHub confirms the site is up and that the site check is still running.

### Practice runs

- Practice alert: Actions tab > Site check > Run workflow > tick "Practice run". It sends a practice alert email and tries the repair tools. Nothing on the site changes.
- Fire drill: Actions tab > Publish guard > Run workflow. It breaks a practice copy on a side branch, confirms the guard repairs it, and removes the side branch. The live site is not touched.

Run both after any change to the files in .github, and once or twice a year.

## If something goes wrong

- **"kensingtonaapac.org needs attention"**: the issue lists what is wrong.
  - The home page did not load: a repair was already tried. Look at githubstatus.com first. If GitHub is fine, open Settings > Pages and confirm the custom domain says kensingtonaapac.org and Enforce HTTPS is ticked.
  - A file did not load: upload that file again.
  - A line starting with DNS: sign in to Porkbun, open the DNS records for the domain and compare them with the list below.
  - HTTPS certificate: GitHub normally renews it on its own. If the warning stays, open Settings > Pages, remove the custom domain, save, add it back and wait up to an hour.
  - Domain registration: renew it at Porkbun.
- **"A change to kensingtonaapac.org was undone automatically"**: the site is fine. Fix what the issue lists and upload the files again.
- **"kensingtonaapac.org had a short problem and recovered"**: a record only. Nothing to do.
- **An email from Google Search Console about "Page with redirect"** that lists the http or www addresses: expected. Those addresses forward to the real one, and Google keeps only the real one in search.
- **Going back to an earlier version by hand**: open the Commits list, find the last version that worked, open index.html there, and upload that copy again.

### DNS records at Porkbun

- A records for kensingtonaapac.org: 185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153 (GitHub Pages)
- CNAME for www: hishamalibob.github.io
- MX: fwd1.porkbun.com and fwd2.porkbun.com (email forwarding for hello@)
- TXT: the SPF line Porkbun added for forwarding, and the google-site-verification line that keeps Search Console connected

### Accounts

The site depends on three sign-ins: GitHub (the files), Porkbun (the domain and email forwarding) and the AAPAC Google account (Search Console and the forms). Keep two-step sign-in on for all three, and keep the recovery email and phone current.
