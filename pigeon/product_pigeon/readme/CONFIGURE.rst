De publieke Wikimedia-API's vereisen geen API-sleutel. De Odoo-server moet wel
uitgaande HTTPS-verbindingen kunnen maken met:

* ``en.wikipedia.org``
* ``www.wikidata.org``
* ``commons.wikimedia.org``

Na installatie kan een beheerder met developer mode de Scheduled Action vinden
via ``Settings > Technical > Scheduled Actions``. De actie heet
``Product Pigeon: Import pigeon products`` en staat standaard actief met een
dagelijks interval.

De API's kunnen tijdelijk HTTP-status 429 retourneren. De module wacht in dat
geval automatisch en probeert de aanvraag maximaal viermaal opnieuw.
