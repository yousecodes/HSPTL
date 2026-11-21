"""Conservative RSS/Atom ingestion for explicitly registered UCKS feeds."""
from __future__ import annotations
import hashlib
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

MAX_FEED_BYTES = 2_000_000


def validate_feed_url(url: str) -> str:
    value = (url or '').strip()
    parsed = urlparse(value)
    if parsed.scheme not in {'https', 'http'} or not parsed.hostname:
        raise ValueError('Feed locator must be an absolute HTTP(S) URL')
    if parsed.username or parsed.password:
        raise ValueError('Credentials in feed URLs are not permitted')
    return value


def parse_feed(payload: bytes) -> list[dict[str, str]]:
    if len(payload) > MAX_FEED_BYTES:
        raise ValueError('Feed exceeds the 2 MB import limit')
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError('Feed is not valid RSS or Atom XML') from exc
    def local(tag: str) -> str:
        return tag.rsplit('}', 1)[-1].lower()
    items = []
    for node in root.iter():
        if local(node.tag) not in {'item', 'entry'}:
            continue
        fields = {}
        links = []
        for child in list(node):
            key = local(child.tag)
            value = ''.join(child.itertext()).strip()
            if key == 'link':
                href = child.attrib.get('href', '').strip()
                if href:
                    links.append(href)
                elif value:
                    links.append(value)
            elif key in {'title', 'description', 'summary', 'content', 'published', 'updated', 'pubdate', 'id', 'guid', 'category'}:
                fields[key] = value
        title = fields.get('title', '').strip()
        body = fields.get('content') or fields.get('description') or fields.get('summary') or ''
        url = next((x for x in links if x.startswith(('https://', 'http://'))), '')
        external = fields.get('id') or fields.get('guid') or url or hashlib.sha256((title+body).encode()).hexdigest()
        if title and body:
            # Strip markup conservatively; retain text without executing embedded content.
            body = re.sub(r'<[^>]*>', ' ', body)
            body = re.sub(r'\s+', ' ', body).strip()
            items.append({'title': title[:500], 'body': body[:100_000], 'url': url,
                          'external_id': external[:1000],
                          'publication_date': fields.get('published') or fields.get('updated') or fields.get('pubdate') or '',
                          'category': fields.get('category', '')})
    return items
