De dagelijkse import wordt automatisch uitgevoerd door de Scheduled Action.

Een beheerder kan de import handmatig testen:

#. Activeer developer mode.
#. Ga naar ``Settings > Technical > Scheduled Actions``.
#. Open ``Product Pigeon: Import pigeon products``.
#. Klik op ``Run Manually``.
#. Controleer het Odoo-log op het aantal ontvangen, aangemaakte en overgeslagen
   rassen.

De geïmporteerde producten zijn beschikbaar via het standaard productmenu,
bijvoorbeeld ``Inventory > Products > Products``. Gebruik het zoekfilter
``Pigeons`` om alleen de door deze module geïmporteerde records te tonen.

Open een product en kies het tabblad ``Pigeon API`` om het Wikipedia page-ID,
Wikidata-ID, de beschikbare herkomst, de Wikipedia-bron, de Commons-thumbnail
en de Wikipedia-beschrijving te bekijken.

Een tweede import met ongewijzigde API-data maakt geen nieuwe producten aan.
De bestaande records worden herkend aan hun unieke ``pigeon_api_id``.
