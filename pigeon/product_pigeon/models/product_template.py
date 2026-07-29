import requests
import time

from lxml import html
from odoo import api, fields, models
from odoo.exceptions import UserError


WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
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
            "prop": "text",
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

        page_html = response.json().get("parse", {}).get("text", "")

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
   
    @api.model
    def _add_wikidata_origins(self, breeds):
        wikidata_ids = [
            breed["wikidata_id"]
            for breed in breeds
            if breed["wikidata_id"]
        ]

        if not wikidata_ids:
            return

        entities = {}

        for offset in range(0, len(wikidata_ids), 50):
            id_batch = wikidata_ids[offset : offset + 50]

            params = {
                "action": "wbgetentities",
                "ids": "|".join(id_batch),
                "props": "claims",
                "format": "json",
            }

            try:
                response = requests.get(
                    WIKIDATA_API_URL,
                    params=params,
                    headers={"User-Agent": USER_AGENT},
                    timeout=20,
                )
                response.raise_for_status()
            except requests.RequestException as error:
                raise UserError(
                    self.env._(
                        "Wikidata could not be reached: %s",
                        error,
                    )
                ) from error

            entities.update(
                response.json().get("entities", {})
            )

            time.sleep(1)

        breed_origin_ids = {}
        all_origin_ids = set()

        for breed in breeds:
            wikidata_id = breed["wikidata_id"]
            entity = entities.get(wikidata_id, {})

            origin_ids = []

            for claim in entity.get("claims", {}).get("P495", []):
                value = (
                    claim.get("mainsnak", {})
                    .get("datavalue", {})
                    .get("value", {})
                )

                if isinstance(value, dict) and value.get("id"):
                    origin_ids.append(value["id"])
                    all_origin_ids.add(value["id"])

            breed_origin_ids[wikidata_id] = origin_ids

        if not all_origin_ids:
            return

        label_params = {
            "action": "wbgetentities",
            "ids": "|".join(sorted(all_origin_ids)),
            "props": "labels",
            "languages": "en",
            "format": "json",
        }

        try:
            label_response = requests.get(
                WIKIDATA_API_URL,
                params=label_params,
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
            label_response.raise_for_status()
        except requests.RequestException as error:
            raise UserError(
                self.env._(
                    "Wikidata labels could not be reached: %s",
                    error,
                )
            ) from error

        label_entities = label_response.json().get(
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
    def _import_pigeon_products(self):
        breeds = self._fetch_pigeon_breeds()
        self._add_wikidata_origins(breeds)

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
            existing_products.mapped("pigeon_api_id")
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
                    "pigeon_origin": breed.get("origin", ""),
                    "pigeon_wikidata_id": breed["wikidata_id"],
                    "pigeon_source_url": breed["source_url"],
                    "description_sale": breed["description"],
                    "list_price": 0.0,
                    "sale_ok": True,
                    "purchase_ok": False,
                }
            )

        if product_values:
            self.create(product_values)

        return len(product_values)