"""Generic adapter for government sites with mailto links.

Works on any HTML page where council members have:
  - Names in bold/strong/heading tags
  - Email addresses as mailto: links
  - Optionally phone numbers as tel: links or plain text

Extends the Revize adapter's marker-based parsing with wider content
area detection to handle WordPress, Drupal, custom sites, etc.

adapterConfig fields:
  - contentSelector: (optional) CSS selector for the content area
  - memberFilter: (optional) list of title substrings to EXCLUDE
    (default: ["clerk", "administrator", "manager", etc.])
"""

from bs4 import BeautifulSoup

from .revize import RevizeAdapter


class GenericMailtoAdapter(RevizeAdapter):
    """Generic scraper for any page with mailto links paired with names."""

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")

        # Try custom selector first, then a wide range of common containers
        custom = self.config.get("contentSelector")
        if custom:
            content = soup.select_one(custom)
        else:
            content = None

        if not content:
            content = (
                # Revize
                soup.find("div", class_="fr-view")
                or soup.find("div", id="divContent")
                or soup.find("div", class_="cms-area")
                # WordPress
                or soup.find("div", class_="entry-content")
                or soup.find("div", class_="et_pb_section")  # Divi
                or soup.find("div", class_="elementor-widget-wrap")
                or soup.find("div", class_="wpb_wrapper")
                # Drupal
                or soup.find("div", class_="field--name-body")
                or soup.find("div", class_="node__content")
                or soup.find("div", class_="view-content")
                # Granicus / generic
                or soup.find("div", class_="content_area")
                or soup.find("div", id="content")
                or soup.find("div", class_="content")
                or soup.find("article")
                or soup.find("main")
                or soup.body
            )

        if not content:
            raise RuntimeError(f"Could not find content area for {self.id}")

        # Use parent class's marker-based parsing logic
        # Temporarily swap the content in, call the parent's parse with a
        # modified HTML where we only keep the content area
        html_subset = str(content)
        return super().parse(f"<body>{html_subset}</body>")
