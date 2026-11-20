from urllib.parse import urlparse, urljoin, urldefrag
from urllib.robotparser import RobotFileParser
import httpx
from bs4 import BeautifulSoup
from .config import USER_AGENT, CRAWL_TIMEOUT, MAX_CRAWL_PAGES
from .processing import clean_text, detect_language, digest
from .db import db

def valid_public_url(url):
    p = urlparse(url)
    return p.scheme in ("http", "https") and bool(p.hostname) and not p.username and not p.password

async def crawl_site(start_url, max_pages=5):
    if not valid_public_url(start_url):
        raise ValueError("Use a valid public HTTP/HTTPS URL.")
    parsed = urlparse(start_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    rp = RobotFileParser()
    async with httpx.AsyncClient(timeout=CRAWL_TIMEOUT, follow_redirects=True,
                                 headers={"User-Agent": USER_AGENT}) as client:
        robots = await client.get(origin + "/robots.txt")
        if robots.status_code >= 400:
            raise ValueError("Cannot verify robots.txt; collection stopped.")
        rp.parse(robots.text.splitlines())
        queue, seen = [start_url], set()
        found = saved = 0
        limit = min(max(1, int(max_pages)), MAX_CRAWL_PAGES)
        while queue and found < limit:
            url = urldefrag(queue.pop(0))[0]
            if url in seen or not valid_public_url(url) or urlparse(url).netloc != parsed.netloc:
                continue
            seen.add(url)
            if not rp.can_fetch(USER_AGENT, url):
                continue
            try:
                response = await client.get(url)
                if response.status_code >= 400 or "text/html" not in response.headers.get("content-type", ""):
                    continue
            except httpx.HTTPError:
                continue
            found += 1
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                tag.decompose()
            title = soup.title.get_text(" ", strip=True) if soup.title else url
            main = soup.find("main") or soup.find("article") or soup.body or soup
            text = clean_text(main.get_text("\n", strip=True))
            if len(text) >= 250:
                try:
                    with db() as con:
                        con.execute("""INSERT INTO documents(title,source,source_type,language,content,status,content_hash)
                            VALUES(?,?,?,?,?,'pending',?)""",
                            (title[:250], url, "web", detect_language(text), text, digest(text)))
                    saved += 1
                except Exception as exc:
                    if "UNIQUE" not in str(exc):
                        raise
            for a in soup.find_all("a", href=True):
                target = urldefrag(urljoin(url, a["href"]))[0]
                if valid_public_url(target) and urlparse(target).netloc == parsed.netloc and target not in seen and target not in queue:
                    queue.append(target)
    return {"pages_found": found, "pages_saved": saved}
