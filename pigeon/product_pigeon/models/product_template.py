import requests
import time

from odoo import api, fields, models
from odoo.exceptions import UserError


WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "ProductPigeon/1.0"
PAGE_BATCH_SIZE = 35

class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_pigeon = fields.Boolean(
        string="Is a Pigeon",
        copy=False,
    )
    pigeon_api_id = fields.Char(
        string="Pigeon API ID",
        copy=False,
        index=True,
    )
    pigeon_origin = fields.Char(
        string="Origin",
    )
    pigeon_wikidata_id = fields.Char(
        string="Wikidata ID",
        copy=False,
    )
    pigeon_source_url = fields.Char(
        string="Wikipedia Source",
    )
    pigeon_image_url = fields.Char(
        string="Commons Image",
    )

    _pigeon_api_id_unique = models.Constraint(
        "UNIQUE(pigeon_api_id)",
        "A product with this pigeon API ID already exists.",
    )

    @api.model
    def _fetch_pigeon_breeds(self):
        params = {
            "action": "parse",
            "page": "List of pigeon breeds",
            "prop": "links",
            "format": "json",
            "formatversion": 2,
        }

        try:
            response = requests.get(
                WIKIPEDIA_API_URL,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise UserError(
                self.env._("Wikipedia could not be reached: %s", error)
            ) from error

        links = response.json().get("parse", {}).get("links", [])

        titles = {
            link["title"]
            for link in links
            if link.get("ns") == 0
            and "exists" in link
            and link.get("title")
        }

        breeds = []
        sorted_titles = sorted(titles)

        for offset in range(0, len(sorted_titles), PAGE_BATCH_SIZE):
            title_batch = sorted_titles[offset : offset + PAGE_BATCH_SIZE]

            detail_params = {
                "action": "query",
                "titles": "|".join(title_batch),
                "prop": "extracts|pageprops|info|pageimages",
                "exintro": 1,
                "explaintext": 1,
                "inprop": "url",
                "piprop": "name",
                "redirects": 1,
                "format": "json",
                "formatversion": 2,
            }

            try:
                detail_response = requests.get(
                    WIKIPEDIA_API_URL,
                    params=detail_params,
                    headers={"User-Agent": USER_AGENT},
                    timeout=20,
                )
                detail_response.raise_for_status()
            except requests.RequestException as error:
                raise UserError(
                    self.env._("Wikipedia details could not be reached: %s", error)
                ) from error

            pages = detail_response.json().get("query", {}).get("pages", [])

            for page in pages:
                if page.get("missing") or not page.get("pageid"):
                    continue

                breeds.append(
                    {
                        "api_id": str(page["pageid"]),
                        "name": page["title"],
                        "description": page.get("extract", ""),
                        "source_url": page.get("fullurl", ""),
                        "wikidata_id": page.get("pageprops", {}).get(
                            "wikibase_item",
                            "",
                        ),
                        "image_title": page.get("pageimage", ""),
                    }
                )

            time.sleep(1)

        unique_breeds = {
            breed["api_id"]: breed
            for breed in breeds
        }

        return list(unique_breeds.values())