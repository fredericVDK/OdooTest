from odoo import fields, models

class ProductTemplate(models.Model):
    #_inherit omdat we de bestaande product.template willen uitbreiden met extra velden voor de pigeon module en geen nieuwe model willen maken.
    _inherit = "product.template"

    is_pigeon = fields.Boolean(
        string="Is a Pigeon",
        copy=False, #word niet gekopieerd bij dupliceren van product
    )
    pigeon_api_id = fields.Char(
        string="Pigeon API ID",
        copy=False, #word niet gekopieerd bij dupliceren van product
        index=True,
    )
    pigeon_origin = fields.Char(
        string="Origin",
        copy=False, #word niet gekopieerd bij dupliceren van product
    )
    pigeon_wikidata_id = fields.Char(
        string="Wikidata ID",
        copy=False, #word niet gekopieerd bij dupliceren van product
    )
    pigeon_source_url = fields.Char(
        string="Wikipedia Source",
        copy=False, #word niet gekopieerd bij dupliceren van product
    )
    pigeon_image_url = fields.Char(
        string="Commons Image",
        copy=False, #word niet gekopieerd bij dupliceren van product
    )

    # Dit zorgt ervoor dat er geen duplicaten van producten met dezelfde pigeon_api_id kunnen worden aangemaakt.
    _pigeon_api_id_unique = models.Constraint(
        "UNIQUE(pigeon_api_id)",
        "A product with this pigeon API ID already exists.",
    )