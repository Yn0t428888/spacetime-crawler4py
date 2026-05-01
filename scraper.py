import re
from urllib.parse import urlparse, urljoin, urldefrag, parse_qs

from bs4 import BeautifulSoup

ALLOWED_DOMAINS = {
    "ics.uci.edu",
    "cs.uci.edu",
    "informatics.uci.edu",
    "stat.uci.edu",
}

ALLOWED_PREFIXES = {
    "today.uci.edu": "/department/information_computer_sciences/",
}

UNIQUE_PAGES_FILE = "unique_pages.txt"

def scraper(url, resp):
    record_unique_page(url, resp)

    links = extract_next_links(url, resp)

    valid_links = []

    for link in links:
        if isinstance(link, str) and is_valid(link):
            valid_links.append(link)

    return valid_links

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content

    if resp is None:
        return []

    if resp.status != 200:
        return []

    if resp.raw_response is None:
        return []

    if resp.raw_response.content is None:
        return []

    content = resp.raw_response.content

    #empty page
    if len(content) == 0:
        return []
    #dont go onto super large pages
    if len(content) > 5000000:
        return []

    try:
        soup = BeautifulSoup(content, "lxml")
    except Exception:
        try:
            soup = BeautifulSoup(content, "html.parser")
        except Exception:
            return []

    links = set()

    #use final URL after redirects when available
    base_url = resp.raw_response.url if resp.raw_response.url else url

    for tag in soup.find_all("a", href=True):
        href = tag.get("href")

        if not href:
            continue

        href = href.strip()

        #skip non-webpage links
        if href.startswith(("mailto:", "javascript:", "tel:", "sms:")):
            continue

        #convert relative link to absolute link
        absolute_url = urljoin(base_url, href)

        #remove fragment, e.g. /page#section -> /page
        absolute_url, _ = urldefrag(absolute_url)

        #remove extra whitespace
        absolute_url = absolute_url.strip()

        if absolute_url:
            links.add(absolute_url)

    return list(links)

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        parsed = urlparse(url)

        if parsed.scheme not in {"http", "https"}:
            return False

        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        query = parsed.query.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        # Allowed domains

        allowed = False

        if domain in ALLOWED_DOMAINS:
            allowed = True

        if any(domain.endswith("." + allowed_domain) for allowed_domain in ALLOWED_DOMAINS):
            allowed = True

        if domain in ALLOWED_PREFIXES:
            if path.startswith(ALLOWED_PREFIXES[domain]):
                allowed = True

        if not allowed:
            return False

        #known traps

        #Calendar/event traps

        #Use /events/ instead of /event/ because /event/
        if "/events/" in path or path.endswith("/events"):
            return False

        #iCal and The Events Calendar plugin traps
        if "ical" in path or "ical" in query:
            return False

        if "tribe" in path or "tribe" in query:
            return False

        #DokuWiki trap
        if "doku.php" in path:
            return False

        #Eppstein
        if domain == "ics.uci.edu" and path.startswith("/~eppstein/pix"):
            return False

        #specific known trap
        if domain == "fano.ics.uci.edu" and path.startswith("/ca/rules"):
            return False

        #GitLab trap: commits/repositories can explode into many pages
        if domain == "gitlab.ics.uci.edu":
            return False

        #grape trap
        if domain == "grape.ics.uci.edu":
            return False

        #ISG events trap
        if domain == "isg.ics.uci.edu" and path.startswith("/events"):
            return False

        #File type filtering
        if re.match(
                r".*\.(css|js|bmp|gif|jpe?g|ico"
                r"|png|tiff?|mid|mp2|mp3|mp4"
                r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv"
                r"|pdf|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx"
                r"|names|data|dat|exe|bz2|tar|msi|bin|7z|psd"
                r"|dmg|iso|epub|dll|cnf|tgz|sha1|thmx|mso"
                r"|arff|rtf|jar|csv|rm|smil|wmv|swf|wma"
                r"|zip|rar|gz|war|apk|img|sql|db|sqlite)$",
                path,
        ):
            return False

        #generic trap prevention

        #long URLs are often traps
        if len(url) > 250:
            return False

        #too many query parameters is sus
        query_params = parse_qs(query)

        if len(query_params) > 3:
            return False

        bad_query_keys = {
            "replytocom",
            "share",
            "sort",
            "filter",
            "session",
            "sid",
            "phpsessid",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "fbclid",
            "gclid",
        }

        if any(key.lower() in bad_query_keys for key in query_params):
            return False

        #avoid search/result pages with many generated combinations
        if "search" in path or "search" in query:
            return False

        #avoid login/logout/admin/account pages
        bad_path_keywords = [
            "login",
            "logout",
            "signup",
            "register",
            "wp-admin",
            "wp-login",
            "admin",
            "account",
            "cart",
            "checkout",
        ]

        if any(keyword in path for keyword in bad_path_keywords):
            return False

        #avoid deep paths
        segments = [segment for segment in path.split("/") if segment]

        if len(segments) > 10:
            return False

        #avoid repeated path segment traps
        segment_counts = {}

        for segment in segments:
            segment_counts[segment] = segment_counts.get(segment, 0) + 1

            if segment_counts[segment] >= 3:
                return False

        #avoid obvious date/calendar archive patterns
        if re.search(r"/\d{4}/\d{1,2}/\d{1,2}", path):
            return False

        if re.search(r"/\d{4}-\d{1,2}-\d{1,2}", path):
            return False

        if re.search(r"[?&](date|month|year|yr)=", "?" + query):
            return False

        return True

    except (TypeError, ValueError):
        return False

def record_unique_page(url, resp):
    """
    Records each successfully crawled unique page.

    Uniqueness is based only on the URL after removing the fragment.
    Example:
    http://www.ics.uci.edu#aaa
    http://www.ics.uci.edu#bbb

    Both count as:
    http://www.ics.uci.edu
    """
    if resp is None:
        return

    if resp.status != 200:
        return

    if resp.raw_response is None:
        return

    if resp.raw_response.content is None:
        return

    if len(resp.raw_response.content) == 0:
        return

    final_url = resp.raw_response.url if resp.raw_response.url else url

    # Remove fragment
    final_url, _ = urldefrag(final_url)
    final_url = final_url.strip()

    if not final_url:
        return

    # Only count pages that your crawler considers valid
    if not is_valid(final_url):
        return

    # Load existing unique URLs
    unique_urls = set()

    try:
        with open(UNIQUE_PAGES_FILE, "r", encoding="utf-8") as f:
            for line in f:
                existing_url = line.strip()
                if existing_url:
                    unique_urls.add(existing_url)
    except FileNotFoundError:
        pass

    # Add current page
    unique_urls.add(final_url)

    # Rewrite file in sorted order so it stays clean
    with open(UNIQUE_PAGES_FILE, "w", encoding="utf-8") as f:
        for unique_url in sorted(unique_urls):
            f.write(unique_url + "\n")

    # Optional live count file
    with open("unique_pages_count.txt", "w", encoding="utf-8") as f:
        f.write(str(len(unique_urls)) + "\n")