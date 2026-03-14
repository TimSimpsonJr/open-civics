"""Adapter for Colleton County Council members.

Scrapes a Drupal site using the Views module. Same structure as
Newberry County with semantic CSS classes for each field:
  - views-field-title: member name
  - views-field-field-job-title: seat/role (e.g. "Seat #4 Western")
  - views-field-field-email-address: email (mailto link)
  - views-field-field-phone-numbers: phone (tel link, may be empty)

Note: Colleton does not use a views-field-field-district class;
the seat/district info is in the job title field.
"""

from .drupal_views import DrupalViewsAdapter


class ColletonCountyAdapter(DrupalViewsAdapter):
    """Scraper for Colleton County Council members.

    Uses the shared DrupalViewsAdapter with views-field pattern.
    """
    pass
