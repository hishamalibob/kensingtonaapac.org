#!/usr/bin/env python3
"""Health checks for kensingtonaapac.org.

  check.py files DIR [--baseline DIR] [--out FILE]
      Looks at the site files in DIR (a copy of this repository) and reports
      anything that would break the live site if it were published.

  check.py live [--repo DIR] [--out FILE]
      Looks at the live site from the outside, the way a visitor reaches it.

Prints one line per problem. Exit status: 0 no problems, 10 problems found,
anything else means the checker itself could not run. Uses only the Python
standard library.
"""

import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

DOMAIN = "kensingtonaapac.org"
SITE = os.environ.get("SITE", "https://" + DOMAIN).rstrip("/")
HOST = urllib.parse.urlsplit(SITE).netloc

# What the domain's DNS should say. If any of this changes on purpose,
# change it here in the same update.
GITHUB_PAGES_IPS = {"185.199.108.153", "185.199.109.153", "185.199.110.153", "185.199.111.153"}
WWW_TARGET = "hishamalibob.github.io"
MAIL_SERVERS = {"fwd1.porkbun.com", "fwd2.porkbun.com"}

PAGES = ["index.html", "privacy.html", "404.html"]
REQUIRED_FILES = ["index.html", "privacy.html", "404.html", "CNAME", "calendar.ics", "robots.txt", "sitemap.xml"]
MIN_HOME_BYTES = 20000
CERT_WARN_DAYS = 14
DOMAIN_WARN_DAYS = 60
RETRY_WAIT = float(os.environ.get("CHECK_RETRY_WAIT", "20"))
USER_AGENT = "kensingtonaapac-site-check (+https://kensingtonaapac.org)"
FOUND_PROBLEMS = 10  # exit status; a crash exits with 1 or 2, which must not look the same

SKIP_SCHEMES = ("http:", "https:", "mailto:", "tel:", "sms:", "data:", "javascript:", "webcal:", "blob:", "about:")
CSS_URL = re.compile(r"""url\(\s*(?:"([^"]*)"|'([^']*)'|([^)'"\s]+))\s*\)""")


class Page(HTMLParser):
    """Collects what a page points to, and its inline scripts."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs = []
        self.ids = set()
        self.anchors = set()
        self.scripts = []
        self.css = []
        self.meta = {}
        self.canonical = None
        self.title = ""
        self._open = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if a.get("id"):
            self.ids.add(a["id"])
        if a.get("name") and tag == "a":
            self.ids.add(a["name"])
        if a.get("href", "").startswith("#") and len(a["href"]) > 1:
            self.anchors.add(urllib.parse.unquote(a["href"][1:]))
        for key in ("href", "src", "poster"):
            if a.get(key):
                self.refs.append(a[key])
        for key in ("srcset", "imagesrcset"):
            for part in a.get(key, "").split(","):
                bits = part.split()
                if bits:
                    self.refs.append(bits[0])
        if tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            if name:
                self.meta[name] = a.get("content", "")
        if tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.canonical = a.get("href")
        if a.get("style"):
            self.css.append(a["style"])
        if tag in ("script", "style", "title"):
            self._open = (tag, a)
            self._buf = []

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in ("script", "style", "title"):
            self._open = None

    def handle_data(self, data):
        if self._open:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if not self._open or self._open[0] != tag:
            return
        text = "".join(self._buf)
        attrs = self._open[1]
        if tag == "script" and not attrs.get("src"):
            self.scripts.append((attrs.get("type", "").strip().lower(), text))
        elif tag == "style":
            self.css.append(text)
        elif tag == "title":
            self.title = text.strip()
        self._open = None

    def local_paths(self):
        """Every file on this site that the page asks a browser to load."""
        found = list(self.refs)
        for block in self.css:
            for m in CSS_URL.finditer(block):
                found.append(m.group(1) or m.group(2) or m.group(3) or "")
        for key in ("og:image", "twitter:image"):
            if self.meta.get(key):
                found.append(self.meta[key])
        paths = set()
        for ref in found:
            path = to_local_path(ref)
            if path:
                paths.add(path)
        return sorted(paths)


def to_local_path(ref):
    """Turn a link into a path inside the site, or None if it leaves the site."""
    ref = ref.strip()
    if not ref or ref.startswith("#") or ref.startswith("%23"):
        return None
    for prefix in (SITE + "/", "https://" + DOMAIN + "/", "https://www." + DOMAIN + "/"):
        if ref.startswith(prefix):
            ref = "/" + ref[len(prefix):]
            break
    else:
        if ref.rstrip("/") in (SITE, "https://" + DOMAIN):
            ref = "/"
    low = ref.lower()
    if low.startswith(SKIP_SCHEMES) or low.startswith("//"):
        return None
    path = urllib.parse.unquote(ref.split("#", 1)[0].split("?", 1)[0]).lstrip("/")
    if path == "" or path.endswith("/"):
        path += "index.html"
    if ".." in path.split("/"):
        return None
    return path


def parse_page(text):
    page = Page()
    page.feed(text)
    page.close()
    return page


def script_problems(name, page):
    """Inline scripts must be valid, or the dates and menus stop working."""
    problems = []
    node = shutil.which("node")
    for kind, text in page.scripts:
        if not text.strip():
            continue
        if kind in ("application/ld+json", "application/json"):
            try:
                json.loads(text)
            except ValueError as err:
                problems.append(f"{name}: the search-engine data block is not valid JSON ({err}).")
        elif kind in ("", "text/javascript", "application/javascript", "module") and node:
            suffix = ".mjs" if kind == "module" else ".js"
            with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8") as tmp:
                tmp.write(text)
            try:
                run = subprocess.run([node, "--check", tmp.name], capture_output=True, text=True, timeout=60)
                if run.returncode != 0:
                    lines = [ln for ln in run.stderr.splitlines() if "Error" in ln]
                    why = lines[0].strip() if lines else "syntax error"
                    problems.append(f"{name}: a script on the page has an error and will not run ({why}).")
            finally:
                os.unlink(tmp.name)
    return problems


def calendar_problems(text, name="calendar.ics"):
    lines = text.replace("\r\n", "\n").split("\n")
    if not text.lstrip().startswith("BEGIN:VCALENDAR") or "END:VCALENDAR" not in text:
        return [f"{name} is not a complete calendar file, so calendar subscriptions would break."]
    problems = []
    begins = sum(1 for ln in lines if ln.strip() == "BEGIN:VEVENT")
    ends = sum(1 for ln in lines if ln.strip() == "END:VEVENT")
    if begins == 0:
        problems.append(f"{name} has no events in it.")
    if begins != ends:
        problems.append(f"{name} has an event that is not closed properly.")
    event = None
    for ln in lines:
        if ln.strip() == "BEGIN:VEVENT":
            event = set()
        elif ln.strip() == "END:VEVENT":
            if event is not None and not {"UID", "DTSTART"} <= event:
                problems.append(f"{name} has an event without a UID or a start time.")
                break
            event = None
        elif event is not None and ln[:1] not in (" ", "\t"):
            event.add(re.split(r"[;:]", ln, maxsplit=1)[0].upper())
    return problems


# ---------------------------------------------------------------- files


def check_files(root, baseline=None):
    problems = []

    def read(name):
        with open(os.path.join(root, name), "rb") as fh:
            return fh.read()

    for name in REQUIRED_FILES:
        if not os.path.isfile(os.path.join(root, name)):
            problems.append(f"{name} is missing.")
    if not os.path.isfile(os.path.join(root, "index.html")):
        return problems

    cname_path = os.path.join(root, "CNAME")
    if os.path.isfile(cname_path) and read("CNAME").decode("utf-8", "replace").strip() != DOMAIN:
        problems.append(f"The CNAME file must contain only {DOMAIN}. Without it the address stops working.")

    home_bytes = read("index.html")
    home = home_bytes.decode("utf-8", "replace")
    if len(home_bytes) < MIN_HOME_BYTES:
        problems.append(f"index.html is only {len(home_bytes):,} bytes. It looks cut off or replaced.")
    if "</html>" not in home[-300:].lower():
        problems.append("index.html does not end properly. The file looks cut off.")
    if baseline and os.path.isfile(os.path.join(baseline, "index.html")):
        before = os.path.getsize(os.path.join(baseline, "index.html"))
        if before >= MIN_HOME_BYTES and len(home_bytes) < before * 0.5:
            problems.append(
                f"index.html shrank from {before:,} to {len(home_bytes):,} bytes in one change. "
                "That usually means part of the page was deleted by accident."
            )

    for name in PAGES:
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            continue
        page = parse_page(read(name).decode("utf-8", "replace"))
        if name == "index.html":
            if "Kensington" not in page.title or "AAPAC" not in page.title:
                problems.append("index.html has lost its page title.")
            if (page.canonical or "").rstrip("/") != SITE:
                problems.append(f"index.html should name {SITE}/ as its main address (the canonical link).")
            if "noindex" in page.meta.get("robots", "").lower():
                problems.append("index.html tells search engines not to list the site (noindex).")
        missing = [p for p in page.local_paths() if not os.path.isfile(os.path.join(root, p))]
        for p in missing[:12]:
            problems.append(f"{name} uses {p}, which is not in the site files.")
        if len(missing) > 12:
            problems.append(f"{name} uses {len(missing) - 12} more files that are not in the site files.")
        gone = sorted(a for a in page.anchors - page.ids if a.lower() != "top")
        for a in gone[:8]:
            problems.append(f"{name} links to the section #{a}, but that section is no longer on the page.")
        problems.extend(script_problems(name, page))

    if os.path.isfile(os.path.join(root, "calendar.ics")):
        problems.extend(calendar_problems(read("calendar.ics").decode("utf-8", "replace")))

    manifest = os.path.join(root, "site.webmanifest")
    if os.path.isfile(manifest):
        try:
            data = json.loads(read("site.webmanifest").decode("utf-8", "replace"))
            for icon in data.get("icons", []):
                p = to_local_path(icon.get("src", ""))
                if p and not os.path.isfile(os.path.join(root, p)):
                    problems.append(f"site.webmanifest uses {p}, which is not in the site files.")
        except ValueError:
            problems.append("site.webmanifest is not valid JSON.")

    if os.path.isfile(os.path.join(root, "sitemap.xml")):
        try:
            tree = ET.fromstring(read("sitemap.xml"))
            locs = [el.text.strip() for el in tree.iter() if el.tag.endswith("}loc") and el.text]
            if SITE + "/" not in locs:
                problems.append(f"sitemap.xml no longer lists {SITE}/.")
        except ET.ParseError:
            problems.append("sitemap.xml is not valid XML.")

    if os.path.isfile(os.path.join(root, "robots.txt")):
        robots = read("robots.txt").decode("utf-8", "replace")
        if re.search(r"(?im)^\s*disallow:\s*/\s*$", robots):
            problems.append("robots.txt tells search engines to stay out of the whole site.")

    return problems


# ----------------------------------------------------------------- live


def fetch(url, tries=3, method="GET", timeout=25):
    """Returns (status, final_url, headers, body). Status 0 means no answer."""
    last = (0, url, {}, b"")
    for attempt in range(tries):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read() if method == "GET" else b""
                return resp.status, resp.geturl(), dict(resp.headers.items()), body
        except urllib.error.HTTPError as err:
            last = (err.code, err.geturl() or url, dict(err.headers.items()) if err.headers else {}, b"")
            if err.code in (404, 410):
                return last
        except Exception as err:  # no answer, DNS failure, bad certificate, timeout
            last = (0, url, {"error": str(getattr(err, "reason", err))}, b"")
        if attempt < tries - 1:
            time.sleep(RETRY_WAIT)
    return last


def cert_days_left(host):
    ctx = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=20) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            cert = tls.getpeercert()
    ends = datetime.datetime.fromtimestamp(ssl.cert_time_to_seconds(cert["notAfter"]), datetime.timezone.utc)
    return (ends - datetime.datetime.now(datetime.timezone.utc)).days, ends.strftime("%b %d, %Y").replace(" 0", " ")


def dns_lookup(name, kind):
    """Returns (ok, answers). ok is False when the lookup service could not be reached."""
    url = "https://dns.google/resolve?" + urllib.parse.urlencode({"name": name, "type": kind})
    status, _, _, body = fetch(url, tries=2, timeout=15)
    if status != 200:
        return False, []
    try:
        data = json.loads(body)
    except ValueError:
        return False, []
    if data.get("Status") not in (0, 3):
        return False, []
    return True, [str(a.get("data", "")).strip().strip('"') for a in data.get("Answer", [])]


def check_dns():
    problems = []
    ok, answers = dns_lookup(DOMAIN, "A")
    if ok:
        ips = {a for a in answers if re.fullmatch(r"[\d.]+", a)}
        if not ips:
            problems.append(f"DNS: {DOMAIN} no longer points anywhere. Check the DNS records at Porkbun (the README lists them).")
        elif not ips <= GITHUB_PAGES_IPS:
            odd = ", ".join(sorted(ips - GITHUB_PAGES_IPS))
            problems.append(f"DNS: {DOMAIN} points to an unexpected address ({odd}). Check the DNS records at Porkbun.")
    ok, answers = dns_lookup("www." + DOMAIN, "CNAME")
    if ok and WWW_TARGET not in {a.rstrip(".").lower() for a in answers}:
        problems.append(f"DNS: www.{DOMAIN} should point to {WWW_TARGET}. Check the DNS records at Porkbun.")
    ok, answers = dns_lookup(DOMAIN, "MX")
    if ok:
        servers = {a.split()[-1].rstrip(".").lower() for a in answers if a}
        if not MAIL_SERVERS <= servers:
            problems.append(f"DNS: the mail records for hello@{DOMAIN} changed, so email to that address may not arrive. Check Email Forwarding at Porkbun.")
    ok, answers = dns_lookup(DOMAIN, "TXT")
    if ok and not any(a.startswith("google-site-verification=") for a in answers):
        problems.append("DNS: the Google verification record is gone, so Search Console will lose access to the site. Add it back at Porkbun (Search Console > Settings > Ownership verification shows the value).")
    return problems


def domain_days_left():
    status, _, _, body = fetch(f"https://rdap.org/domain/{DOMAIN}", tries=1, timeout=25)
    if status != 200:
        return None
    try:
        events = json.loads(body).get("events", [])
    except ValueError:
        return None
    for event in events:
        if event.get("eventAction") == "expiration" and event.get("eventDate"):
            try:
                ends = datetime.datetime.fromisoformat(event["eventDate"].replace("Z", "+00:00"))
            except ValueError:
                return None
            return (ends - datetime.datetime.now(datetime.timezone.utc)).days
    return None


def check_live(repo=None):
    problems = []
    flags = {"down": False, "stale": False}

    status, final, headers, body = fetch(SITE + "/")
    text = body.decode("utf-8", "replace")
    if status != 200 or "AAPAC" not in text or "</html>" not in text[-300:].lower():
        flags["down"] = True
        why = f"status {status}" if status else f"no answer: {headers.get('error', 'unknown error')}"
        if status == 200:
            why = "the page came back incomplete"
        problems.append(f"The home page did not load ({why}).")
    else:
        page = parse_page(text)
        header = " ".join(v for k, v in headers.items() if k.lower() == "x-robots-tag")
        robots = (header + " " + page.meta.get("robots", "")).lower()
        if "noindex" in robots:
            problems.append("The home page tells search engines not to list the site (noindex).")

        paths = [p for p in page.local_paths() if p != "index.html"]
        for extra in ("calendar.ics", "privacy.html", "sitemap.xml", "robots.txt"):
            if extra not in paths:
                paths.append(extra)

        def head(path):
            url = SITE + "/" + urllib.parse.quote(path)
            code = fetch(url, tries=2, method="HEAD")[0]
            if code == 405:
                code = fetch(url, tries=1)[0]
            return path, code

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(head, paths))
        broken = [(p, c) for p, c in results if c != 200]
        for p, c in broken[:12]:
            problems.append(f"{p} did not load (status {c}). The page uses it.")
        if len(broken) > 12:
            problems.append(f"{len(broken) - 12} more files did not load.")

        status_c, _, _, cal = fetch(SITE + "/calendar.ics", tries=2)
        if status_c == 200:
            problems.extend(calendar_problems(cal.decode("utf-8", "replace")))

        if repo and os.path.isfile(os.path.join(repo, "index.html")):
            with open(os.path.join(repo, "index.html"), "rb") as fh:
                wanted = hashlib.sha256(fh.read()).hexdigest()
            if hashlib.sha256(body).hexdigest() != wanted:
                flags["stale"] = True

    # The other ways of typing the address must all land on the real one.
    for other in (f"http://{DOMAIN}/", f"http://www.{DOMAIN}/", f"https://www.{DOMAIN}/"):
        code, landed, hdrs, _ = fetch(other, tries=2)
        if code != 200 or landed.rstrip("/") != SITE:
            if not flags["down"]:
                detail = f"it ended at {landed} with status {code}" if code else f"no answer: {hdrs.get('error', 'unknown error')}"
                problems.append(f"{other} should forward to {SITE}/ but {detail}.")

    for host in (HOST, "www." + HOST):
        try:
            days, ends = cert_days_left(host)
            if days < CERT_WARN_DAYS:
                problems.append(
                    f"The HTTPS certificate for {host} ends in {days} days ({ends}). GitHub normally renews it on its own. "
                    "If this stays, open the repository's Settings > Pages, remove the custom domain, save, and add it back."
                )
        except Exception as err:
            if not flags["down"]:
                problems.append(f"The HTTPS certificate for {host} could not be checked ({err}).")

    left = domain_days_left()
    if left is not None and left < DOMAIN_WARN_DAYS:
        problems.append(f"The domain registration ends in {left} days. Renew it at Porkbun.")

    problems.extend(check_dns())
    return problems, flags


def main():
    parser = argparse.ArgumentParser(description="Health checks for kensingtonaapac.org")
    sub = parser.add_subparsers(dest="mode", required=True)
    files = sub.add_parser("files")
    files.add_argument("dir")
    files.add_argument("--baseline")
    files.add_argument("--out")
    live = sub.add_parser("live")
    live.add_argument("--repo")
    live.add_argument("--out")
    args = parser.parse_args()

    if args.mode == "files":
        problems, flags = check_files(args.dir, args.baseline), {}
    else:
        problems, flags = check_live(args.repo)

    for line in problems:
        print("- " + line)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"problems": problems, **flags}, fh)
    return FOUND_PROBLEMS if problems else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as err:  # the checker failed, which is not the site's fault
        print(f"The checker could not run: {err!r}", file=sys.stderr)
        sys.exit(2)
