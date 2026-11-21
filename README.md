# Kensington Elementary AAPAC website

Source for kensingtonaapac.org, the site of the African American Parent Advisory Council at Kensington Elementary School (West Contra Costa Unified). Hosted on GitHub Pages from this repository. Contact: KensingtonAAPAC@gmail.com

## Files

- index.html: the whole site, one page.
- photos/: Ruby Bridges Walk photos by Ittai Shiu, at 800 and 1600 pixels wide.
- fonts/: Young Serif, Source Serif 4 and Figtree (SIL Open Font License), served from this site.
- aapac-meetings-2026-27.ics, kcsd-board-2026-12-10.ics: calendar files linked from the Dates section.
- og-image.png: the preview image shown when the link is shared.
- banner.jpg, apple-touch-icon.png, robots.txt, sitemap.xml, CNAME.

## Weekly update (about ten minutes)

1. In index.html, find the section with id="this-week".
2. Change the eyebrow line ("Week of ...").
3. Add the newest line at the top of "What we did". Keep what is public: no private conversations, no names of families or children.
4. Rewrite "What comes next", each item with its "Why".
5. In "Coming up" and "Dates", add new items. Each dated item carries data-until="YYYY-MM-DD" and hides itself after that day.
6. Change the "Updated" date in the footer and the lastmod date in sitemap.xml.
