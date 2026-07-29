import time
import logging

import requests
from lxml import html

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"

USER_AGENT = "ProductPigeon/1.0"
PAGE_BATCH_SIZE = 35
MAX_REQUEST_ATTEMPTS = 4

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
    def _request_json(self, url, params, api_name):
        last_error = None

        for attempt in range(MAX_REQUEST_ATTEMPTS):
            response = None

            try:
                response = requests.get(
                    url,
                    params=params,
                    headers={"User-Agent": USER_AGENT},
                    timeout=20,
                )
                response.raise_for_status()

                return response.json()

            except (requests.RequestException, ValueError) as error:
                last_error = error

                status_code = (
                    response.status_code
                    if response is not None
                    else 0
                )

                if (
                    status_code != 429
                    or attempt == MAX_REQUEST_ATTEMPTS - 1
                ):
                    break

                retry_after = response.headers.get(
                    "Retry-After",
                    "",
                )

                if retry_after.isdigit():
                    delay = int(retry_after)
                else:
                    delay = 5 * (attempt + 1)

                time.sleep(delay)

        raise UserError(
            self.env._(
                "%(api_name)s could not be reached: %(error)s",
                api_name=api_name,
                error=last_error,
            )
        ) from last_error

    @api.model
    def _fetch_pigeon_breeds(self):
        list_params = {
            "action": "parse",
            "page": "List of pigeon breeds",
            "prop": "text",
            "format": "json",
            "formatversion": 2,
        }

        list_data = self._request_json(
            WIKIPEDIA_API_URL,
            list_params,
            "Wikipedia",
        )

        page_html = list_data.get(
            "parse",
            {},
        ).get(
            "text",
            "",
        )

        if not page_html:
            raise UserError(
                self.env._(
                    "Wikipedia returned an empty pigeon breed page."
                )
            )

        document = html.fromstring(page_html)

        titles = set(
            document.xpath(
                "//div[contains(@class, 'mw-parser-output')]"
                "/ul/li/a[1]"
                "[starts-with(@href, '/wiki/')]"
                "[not(contains(@class, 'new'))]"
                "/@title"
            )
        )

        breeds = []
        sorted_titles = sorted(titles)

        for offset in range(
            0,
            len(sorted_titles),
            PAGE_BATCH_SIZE,
        ):
            title_batch = sorted_titles[
                offset : offset + PAGE_BATCH_SIZE
            ]

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

            detail_data = self._request_json(
                WIKIPEDIA_API_URL,
                detail_params,
                "Wikipedia details",
            )

            pages = detail_data.get(
                "query",
                {},
            ).get(
                "pages",
                [],
            )

            for page in pages:
                if (
                    page.get("missing")
                    or not page.get("pageid")
                ):
                    continue

                breeds.append(
                    {
                        "api_id": str(page["pageid"]),
                        "name": page["title"],
                        "description": page.get(
                            "extract",
                            "",
                        ),
                        "source_url": page.get(
                            "fullurl",
                            "",
                        ),
                        "wikidata_id": page.get(
                            "pageprops",
                            {},
                        ).get(
                            "wikibase_item",
                            "",
                        ),
                        "image_title": page.get(
                            "pageimage",
                            "",
                        ),
                    }
                )

            time.sleep(1)

        unique_breeds = {
            breed["api_id"]: breed
            for breed in breeds
        }

        return list(unique_breeds.values())

    @api.model
    def _add_wikidata_origins(self, breeds):
        wikidata_ids = sorted(
            {
                breed["wikidata_id"]
                for breed in breeds
                if breed["wikidata_id"]
            }
        )

        if not wikidata_ids:
            return

        entities = {}

        for offset in range(
            0,
            len(wikidata_ids),
            50,
        ):
            id_batch = wikidata_ids[offset : offset + 50]

            params = {
                "action": "wbgetentities",
                "ids": "|".join(id_batch),
                "props": "claims",
                "format": "json",
            }

            data = self._request_json(
                WIKIDATA_API_URL,
                params,
                "Wikidata",
            )

            entities.update(
                data.get(
                    "entities",
                    {},
                )
            )

            time.sleep(1)

        breed_origin_ids = {}
        all_origin_ids = set()

        for breed in breeds:
            wikidata_id = breed["wikidata_id"]
            entity = entities.get(
                wikidata_id,
                {},
            )

            origin_ids = []

            for claim in entity.get(
                "claims",
                {},
            ).get(
                "P495",
                [],
            ):
                value = (
                    claim.get("mainsnak", {})
                    .get("datavalue", {})
                    .get("value", {})
                )

                if (
                    isinstance(value, dict)
                    and value.get("id")
                ):
                    origin_ids.append(value["id"])
                    all_origin_ids.add(value["id"])

            breed_origin_ids[wikidata_id] = origin_ids

        if not all_origin_ids:
            return

        label_params = {
            "action": "wbgetentities",
            "ids": "|".join(
                sorted(all_origin_ids)
            ),
            "props": "labels",
            "languages": "en",
            "format": "json",
        }

        label_data = self._request_json(
            WIKIDATA_API_URL,
            label_params,
            "Wikidata labels",
        )

        label_entities = label_data.get(
            "entities",
            {},
        )

        labels = {
            entity_id: entity.get(
                "labels",
                {},
            ).get(
                "en",
                {},
            ).get(
                "value",
                "",
            )
            for entity_id, entity in label_entities.items()
        }

        for breed in breeds:
            origin_ids = breed_origin_ids.get(
                breed["wikidata_id"],
                [],
            )

            breed["origin"] = ", ".join(
                labels[origin_id]
                for origin_id in origin_ids
                if labels.get(origin_id)
            )

    @api.model
    def _add_commons_image_urls(self, breeds):
        breeds_by_image_title = {
            f"File:{breed['image_title']}": breed
            for breed in breeds
            if breed.get("image_title")
        }

        image_titles = list(breeds_by_image_title)

        for offset in range(0, len(image_titles), 50):
            title_batch = image_titles[offset : offset + 50]

            params = {
                "action": "query",
                "titles": "|".join(title_batch),
                "prop": "imageinfo",
                "iiprop": "url|mime",
                "iiurlwidth": 512,
                "format": "json",
                "formatversion": 2,
            }

            data = self._request_json(
                COMMONS_API_URL,
                params,
                "Wikimedia Commons",
            )

            pages = data.get(
                "query",
                {},
            ).get(
                "pages",
                [],
            )

            for page in pages:
                image_info = page.get("imageinfo", [])

                if not image_info:
                    continue

                image = image_info[0]

                if not image.get("mime", "").startswith("image/"):
                    continue

                breed = breeds_by_image_title.get(
                    page.get("title")
                )

                if breed:
                    breed["image_url"] = image.get(
                        "thumburl",
                        "",
                    )

            time.sleep(1)

    @api.model
    def _import_pigeon_products(self):
        breeds = self._fetch_pigeon_breeds()
        self._add_wikidata_origins(breeds)
        self._add_commons_image_urls(breeds)

        api_ids = [
            breed["api_id"]
            for breed in breeds
        ]

        existing_products = self.search(
            [
                ("pigeon_api_id", "in", api_ids),
            ]
        )

        existing_api_ids = set(
            existing_products.mapped(
                "pigeon_api_id"
            )
        )

        new_breeds = [
            breed
            for breed in breeds
            if breed["api_id"] not in existing_api_ids
        ]

        product_values = []

        for breed in new_breeds:
            product_values.append(
                {
                    "name": breed["name"],
                    "is_pigeon": True,
                    "pigeon_api_id": breed["api_id"],
                    "pigeon_origin": breed.get(
                        "origin",
                        "",
                    ),
                    "pigeon_wikidata_id": breed[
                        "wikidata_id"
                    ],
                    "pigeon_source_url": breed[
                        "source_url"
                    ],
                    "pigeon_image_url": breed.get("image_url", ""),
                    "description_sale": breed[
                        "description"
                    ],
                    "list_price": 0.0,
                    "sale_ok": True,
                    "purchase_ok": False,
                }
            )

        if product_values:
            self.create(product_values)

        _logger.info(
            "Pigeon import finished: %s received, %s created, %s skipped",
            len(breeds),
            len(product_values),
            len(breeds) - len(product_values),
        )
        return len(product_values)
    
    @api.model
    def _cron_import_pigeon_products(self):
        return self._import_pigeon_products()
    