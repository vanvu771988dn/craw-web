# src/utils/html_utils.py

from bs4 import BeautifulSoup
from bs4.element import Tag
import re

NOISE_CLASS_PATTERN = re.compile(
    r"(related|recommended|newsletter|subscribe|comment|cookie|consent|share|social|advert|promo|outbrain|taboola)",
    re.I,
)
NOISE_TAGS = ("script", "style", "nav", "footer", "aside", "form", "noscript")


def remove_noise_nodes(node: BeautifulSoup | Tag) -> BeautifulSoup | Tag:
    """Removes common non-article noise nodes from a soup fragment."""
    for noisy_tag in node.find_all(NOISE_TAGS):
        noisy_tag.decompose()

    for tag in list(node.find_all(True)):
        attr_values = " ".join(
            str(value)
            for key, value in tag.attrs.items()
            if key in {"class", "id", "data-testid", "aria-label"}
        )
        if attr_values and NOISE_CLASS_PATTERN.search(attr_values):
            tag.decompose()

    return node

def clean_html_for_extraction(html: str | None) -> str:
    """
    Cleans the HTML by removing structural and content-noise elements.
    Returns an empty string if the input HTML is None.
    """
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    remove_noise_nodes(soup)
    return str(soup)
