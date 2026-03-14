"""Adapter for Newberry County Council members.

Scrapes a Drupal site using the Views module. Each council member is
rendered in a views-row with semantic CSS classes:
  - views-field-title: member name (link)
  - views-field-field-district: "District N"
  - views-field-field-job-title: role (Chairman, Councilman, etc.)
  - views-field-field-email-address: email (mailto link)
  - views-field-field-phone-numbers: phone (tel link)
"""

from .drupal_views import DrupalViewsAdapter


class NewberryCountyAdapter(DrupalViewsAdapter):
    """Scraper for Newberry County Council members.

    Uses the shared DrupalViewsAdapter with views-field pattern.
    """
    pass
