Product Pigeon
==============

Doel van de module
------------------

``product_pigeon`` importeert duivenrassen uit de publieke API's van
Wikipedia, Wikidata en Wikimedia Commons. Elk ras wordt opgeslagen als een
product in Odoo. Een dagelijkse Scheduled Action controleert de bronnen op
nieuwe rassen en maakt alleen producten aan die nog niet bestaan.

De module gebruikt drie API's:

* Wikipedia levert de lijst met rassen, het unieke page-ID, de naam, een korte
  beschrijving, de bron-URL, het Wikidata-ID en de titel van een gekoppelde
  afbeelding.
* Wikidata levert het land van herkomst via eigenschap ``P495``. Niet iedere
  Wikidata-entiteit bevat deze eigenschap; in dat geval blijft de herkomst
  leeg.
* Wikimedia Commons levert, wanneer beschikbaar, een URL naar een compacte
  thumbnail. De module downloadt geen grote afbeeldingsbestanden naar Odoo.

Productmodel
------------

De module maakt geen afzonderlijk duivenmodel. Ze breidt het bestaande Odoo-
model ``product.template`` uit met ``_inherit``::

    class ProductTemplate(models.Model):
        _inherit = "product.template"

Een duivenras blijft daardoor een volwaardig Odoo-product en kan via de
standaard productmenu's, zoekfuncties en views worden beheerd. Bestaande
productvelden worden hergebruikt:

* ``name`` bevat de naam van het ras.
* ``description_sale`` bevat de inleidende beschrijving van Wikipedia.
* ``list_price`` wordt op ``0.0`` gezet omdat de API geen prijs levert.
* ``sale_ok`` staat aan en ``purchase_ok`` staat uit.

De volgende velden worden door ``product_pigeon`` toegevoegd:

``is_pigeon``
    Technische markering waarmee geïmporteerde duivenproducten kunnen worden
    gefilterd. Het veld gebruikt ``copy=False``, zodat een gekopieerd product
    niet automatisch als API-record wordt behandeld.

``pigeon_api_id``
    Het unieke numerieke page-ID van Wikipedia. Dit is de externe sleutel
    waarmee de import bestaande producten herkent. Het veld heeft een index
    voor snelle zoekopdrachten en gebruikt ``copy=False``.

``pigeon_origin``
    Het land van herkomst dat uit Wikidata-eigenschap ``P495``
    wordt afgeleid.

``pigeon_wikidata_id``
    Het Wikidata-ID van het ras, bijvoorbeeld ``Q12345``. Dit veld gebruikt
    ``copy=False``.

``pigeon_source_url``
    De volledige URL van de Wikipedia-pagina die als bron voor het product is
    gebruikt.

``pigeon_image_url``
    Een URL naar een thumbnail op Wikimedia Commons. Dit veld blijft leeg
    wanneer Wikipedia geen geschikt afbeeldingsbestand koppelt of Commons
    geen geldige afbeelding retourneert.

Voorkomen van duplicaten
------------------------

Duplicaten worden op twee niveaus voorkomen.

De import verzamelt eerst alle Wikipedia page-ID's en zoekt de bestaande
producten in een enkele ORM-query. Alleen rassen waarvan ``pigeon_api_id`` nog
niet bestaat, worden opgenomen in ``product_values`` en aangemaakt.

Daarnaast bevat ``product.template`` een unieke databaseconstraint op
``pigeon_api_id``. Die constraint vormt een laatste bescherming wanneer twee
processen hetzelfde ras gelijktijdig zouden proberen aan te maken. Gewone
producten zonder ``pigeon_api_id`` blijven toegestaan.

API-verwerking
--------------

``_request_json``
~~~~~~~~~~~~~~~~~

Deze centrale helper voert alle HTTP GET-aanvragen uit. Iedere aanvraag bevat
een herkenbare User-Agent en een timeout van twintig seconden. Bij HTTP-status
``429 Too Many Requests`` respecteert de methode de ``Retry-After``-header van
Wikimedia. Wanneer die header ontbreekt, wordt een oplopende wachttijd
gebruikt. Na maximaal vier pogingen wordt een leesbare ``UserError`` aan Odoo
doorgegeven.

``_fetch_pigeon_breeds``
~~~~~~~~~~~~~~~~~~~~~~~~

Deze methode vraagt eerst de HTML van ``List of pigeon breeds`` op. Een XPath-
expressie selecteert alleen bestaande Wikipedia-links uit de eigenlijke
raslijsten. Algemene links en rode links naar pagina's die niet bestaan worden
uitgesloten.

De titels worden daarna in batches van 35 opgevraagd. Voor iedere geldige
pagina worden page-ID, naam, beschrijving, bron-URL, Wikidata-ID en
afbeeldingstitel verzameld.

``_add_wikidata_origins``
~~~~~~~~~~~~~~~~~~~~~~~~~

Deze methode verzamelt alle beschikbare Wikidata-ID's en vraagt de entities in
batches op. Uit de claims wordt eigenschap ``P495`` gelezen. De gevonden
Wikidata-ID's van landen worden in een tweede aanvraag naar
labels vertaald en als ``origin`` aan de tijdelijke rasgegevens toegevoegd.

``_add_commons_image_urls``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

De door Wikipedia geleverde bestandstitels worden in batches van maximaal 50
naar Wikimedia Commons gestuurd. Alleen resultaten waarvan het MIME-type met
``image/`` begint worden aanvaard. Commons genereert een thumbnail met een
breedte van maximaal 512 pixels; de URL hiervan wordt aan de tijdelijke
rasgegevens toegevoegd.

``_import_pigeon_products``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Dit is de centrale importmethode. De methode doorloopt achtereenvolgens de
Wikipedia-, Wikidata- en Commons-verrijking, zoekt bestaande API-ID's, bouwt de
waarden voor nieuwe producten op en maakt die producten met de Odoo ORM aan.

Na iedere uitvoering wordt gelogd hoeveel rassen werden ontvangen, aangemaakt
en overgeslagen. Een tweede uitvoering met ongewijzigde brondata resulteert
bijvoorbeeld in ``152 received, 0 created, 152 skipped``.

``_cron_import_pigeon_products``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Deze kleine wrapper is het publieke startpunt voor de Scheduled Action en
roept de centrale importmethode aan. Hierdoor blijft de crondefinitie eenvoudig
en is uit de methodenaam duidelijk dat ze door een cronjob wordt uitgevoerd.

Scheduled Action
----------------

``data/ir_cron_data.xml`` registreert een actieve Scheduled Action met een
interval van een dag. De actie draait als de Odoo rootgebruiker en voert de
volgende code uit::

    model._cron_import_pigeon_products()


Gebruikersinterface
-------------------

``views/product_template_views.xml`` erft de bestaande productviews:

* Het productformulier krijgt een tabblad ``Pigeon API`` met identificatie,
  herkomst, bronlinks en Wikipedia-beschrijving. Het tabblad is alleen zichtbaar
  wanneer ``is_pigeon`` actief is.
* De productlijst krijgt optionele kolommen voor herkomst en Wikidata-ID.
* De productzoeker krijgt een filter ``Pigeons`` met het domein
  ``[('is_pigeon', '=', True)]``.

Transacties en foutafhandeling
------------------------------

De module gebruikt uitsluitend de Odoo ORM en voert zelf geen databasecommit
uit. Odoo beheert de transactie van de cronjob. Wanneer een API-aanvraag of
databasebewerking mislukt, wordt de volledige uitvoering teruggedraaid. Zo
ontstaan geen gedeeltelijke imports.
