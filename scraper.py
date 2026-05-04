import re
import json
from collections import Counter
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

REPORT_DATA_FILE = "report_data.json"
REPORT_SUMMARY_FILE = "report_summary.txt"

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an",
    "and", "any", "are", "as", "at", "be", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "can", "did", "do",
    "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here",
    "hers", "herself", "him", "himself", "his", "how", "i", "if", "in",
    "into", "is", "it", "its", "itself", "just", "me", "more", "most",
    "my", "myself", "no", "nor", "not", "now", "of", "off", "on",
    "once", "only", "or", "other", "our", "ours", "ourselves", "out",
    "over", "own", "same", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "will",
    "with", "you", "your", "yours", "yourself", "yourselves"
}

def scraper(url, resp):
    update_report(url, resp)

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

        #allowed domains

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


        #/events/
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

        #fano
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

def update_report(url, resp):
    """
    Updates report_data.json and report_summary.txt after each successfully crawled page.

    Tracks:
    1. Unique pages found
    2. Longest page by word count
    3. Top 50 most common words, ignoring stop words
    4. Subdomains in uci.edu and unique page count per subdomain
    """
    if resp is None:
        return

    if resp.status != 200:
        return

    if resp.raw_response is None:
        return

    if resp.raw_response.content is None:
        return

    content = resp.raw_response.content

    if len(content) == 0:
        return

    final_url = resp.raw_response.url if resp.raw_response.url else url

    # Assignment says uniqueness ignores fragments
    final_url, _ = urldefrag(final_url)
    final_url = final_url.strip()

    if not final_url:
        return

    if not is_valid(final_url):
        return

    try:
        soup = BeautifulSoup(content, "lxml")
    except Exception:
        try:
            soup = BeautifulSoup(content, "html.parser")
        except Exception:
            return

    # Remove non-visible or low-value text
    for bad_tag in soup(["script", "style", "noscript"]):
        bad_tag.decompose()

    text = soup.get_text(separator=" ")

    all_words = extract_all_words(text)
    filtered_words = remove_stop_words(all_words)

    # Skip pages with almost no text
    if len(all_words) < 5:
        return

    data = load_report_data()

    # If this exact defragmented URL was already counted, skip it
    if final_url in data["unique_urls"]:
        write_report_summary(data)
        return

    # 1. Unique pages
    data["unique_urls"].append(final_url)

    # 2. Longest page by total word count, before stop-word removal
    word_count = len(all_words)

    if word_count > data["longest_page"]["word_count"]:
        data["longest_page"] = {
            "url": final_url,
            "word_count": word_count
        }

    # 3. Most common words, after stop-word removal
    word_counter = Counter(data["word_counts"])
    word_counter.update(filtered_words)
    data["word_counts"] = dict(word_counter)

    # 4. Subdomain counts
    subdomain = get_subdomain(final_url)

    if subdomain is not None:
        if subdomain not in data["subdomains"]:
            data["subdomains"][subdomain] = []

        data["subdomains"][subdomain].append(final_url)

    save_report_data(data)
    write_report_summary(data)

def extract_all_words(text):
    """
    Extracts words from visible page text.
    HTML markup does not count because BeautifulSoup already removed it.
    """
    return re.findall(r"[a-zA-Z]+", text.lower())


def remove_stop_words(words):
    """
    Removes stop words and one-letter words.
    """
    filtered_words = []

    for word in words:
        if len(word) <= 1:
            continue

        if word in STOP_WORDS:
            continue

        filtered_words.append(word)

    return filtered_words

def load_report_data():
    """
    Loads report data from disk.
    If the file does not exist yet, creates a fresh structure.
    """
    default_data = {
        "unique_urls": [],
        "longest_page": {
            "url": "",
            "word_count": 0
        },
        "word_counts": {},
        "subdomains": {}
    }

    try:
        with open(REPORT_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return default_data
    except json.JSONDecodeError:
        return default_data

    for key in default_data:
        if key not in data:
            data[key] = default_data[key]

    return data


def save_report_data(data):
    """
    Saves the report data to disk.
    """
    with open(REPORT_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_subdomain(url):
    """
    Returns the normalized uci.edu subdomain.

    Example:
    https://vision.ics.uci.edu/page
    becomes:
    vision.ics.uci.edu
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    if domain.endswith("uci.edu"):
        return domain

    return None

def write_report_summary(data):
    """
    Writes the current report answers to report_summary.txt.
    This file is rewritten after each new unique page is processed.
    """
    unique_urls = set(data["unique_urls"])

    word_counter = Counter(data["word_counts"])
    top_50_words = word_counter.most_common(50)

    subdomain_counts = {}

    for subdomain, urls in data["subdomains"].items():
        unique_subdomain_urls = set(urls)
        subdomain_counts[subdomain] = len(unique_subdomain_urls)

    with open(REPORT_SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write("Crawler Report Summary\n")
        f.write("======================\n\n")

        f.write("1. How many unique pages did you find?\n")
        f.write(str(len(unique_urls)) + "\n\n")

        f.write("2. What is the longest page in terms of the number of words?\n")
        f.write("URL: " + data["longest_page"]["url"] + "\n")
        f.write("Word count: " + str(data["longest_page"]["word_count"]) + "\n\n")

        f.write("3. What are the 50 most common words in the entire set of pages crawled?\n")
        for word, count in top_50_words:
            f.write(word + ", " + str(count) + "\n")

        f.write("\n")

        f.write("4. How many subdomains did you find in the uci.edu domain?\n")
        f.write("Total subdomains: " + str(len(subdomain_counts)) + "\n\n")

        for subdomain in sorted(subdomain_counts):
            f.write(subdomain + ", " + str(subdomain_counts[subdomain]) + "\n")