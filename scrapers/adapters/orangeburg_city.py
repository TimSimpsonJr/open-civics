"""Adapter for City of Orangeburg council members.

Scrapes a Drupal site using the Views module with person-item articles.
Each council member is an <article class="person-item"> with:
  - person-item__title: member name (link)
  - person-item__job-title: title (Mayor, District N Seat)
  - person-item__email-address: email (mailto link)
  - person-item__phone-numbers: phone (tel link)
"""

from .drupal_views import DrupalViewsAdapter


class OrangeburgCityAdapter(DrupalViewsAdapter):
    """Scraper for City of Orangeburg council members.

    Uses the shared DrupalViewsAdapter with person-item pattern
    (auto-detected).
    """
    pass
