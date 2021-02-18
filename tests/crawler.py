#!env python
from mechanize import Browser
from urllib.error import HTTPError, URLError
import re
import sys
import urllib.parse

base = "http://localhost:5000"


def click_all_links(brower, url, seen_links, depth=0):
    full_url = urllib.parse.urljoin(base, url)
    if re.match(r"^[mailto.*|#.*]", url):
        return None

    leader = "-" * (depth + 1)
    print("%s Opening %s" % (leader, full_url))
    try:
        br.open(full_url)
    except (URLError, HTTPError) as e:
        print(e)
        sys.exit(1)

    for link in br.links():
        if link.url in ["/login", "/logout", "/admin"]:
            continue

        # skip player links
        if re.match(r"\/p\/\w{8}",  link.url):
            continue

        if link.url not in seen_links:
            seen_links.append(link.url)
            new_depth = depth + 1
            click_all_links(br, link.url, seen_links, new_depth)
        else:
            continue

    return len(seen_links)


br = Browser()
length = click_all_links(br, "", [])
print("Scanned %s links without issue" % length)
