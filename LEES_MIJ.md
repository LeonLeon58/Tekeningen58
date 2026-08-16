# Getekend — automatische site-generator

Dit script bouwt je hele "Getekend"-website in één keer op uit een map met
foto's, zonder dat ik (Claude) er nog per tekenaar bij hoef te typen. Zo
kun je duizenden foto's verwerken zonder de upload-limiet per chatsessie
tegen te komen — je doet het voortaan lokaal, op je eigen computer.

## Wat je nodig hebt

- Python 3 (die heb je waarschijnlijk al)
- De library "Pillow": open een terminal en typ `pip install Pillow`

## Zo gebruik je het

1. Zet ALLE foto's (met hun originele bestandsnamen) in één map,
   bijvoorbeeld een map die je "foto's" noemt.
2. Open een terminal in de map met `build_site.py` en typ:

   python3 build_site.py foto's/

3. Klaar. Er verschijnt een map `images/` en een bestand `index.html`.
   Dubbelklik op `index.html` om de site te bekijken.

Voeg je later nieuwe foto's toe? Zet ze gewoon bij de rest in de map en
draai het commando opnieuw — het hele archief wordt herbouwd, inclusief
je nieuwe foto's, in dezelfde alfabetische volgorde.

## Bestandsnaam-conventie (belangrijk!)

Het script herkent tekenaar/festival/type aan de bestandsnaam. Voor 100%
betrouwbare herkenning, gebruik precies dit patroon:

    Achternaam__Voornaam.jpg
        -> portret, zonder festival

    Achternaam__Voornaam__Locatie__JJ_.jpg
        -> portret, met festival (JJ = laatste 2 cijfers van het jaar)

    Achternaam__Voornaam_-_Titel.jpg
        -> cover van boek "Titel"

    Achternaam__Voornaam_-_Titel_tek__Locatie__JJ_.jpg
        -> een getekende opdracht in "Titel", met festival
           (het woordje "tek" is de sleutel: dat vertelt het script
            dat dit een tekening/opdracht is, geen cover)

Let op:
- Gebruik ALTIJD dubbele underscores (__) tussen Achternaam en Voornaam,
  en tussen Titel/tek en Locatie/Jaar.
- Gebruik ALTIJD "_-_" (underscore-streepje-underscore) vóór de titel.
- Binnen een naam met meerdere woorden (zoals "Lys lez Lannoy") gebruik
  je gewone enkele underscores.

Als je je oudere, wat inconsistent genoemde bestanden er nu al bij zet:
geen paniek. Het script doet een goede gok, en bestanden die het niet
kon plaatsen komen in `review.txt` te staan — die kun je met de hand
hernoemen en opnieuw laten verwerken.

## Wat het script NIET doet

- Het overschrijft geen bestaande, met de hand aangepaste index.html
  zonder toestemming: het herbouwt 'm gewoon opnieuw vanuit de foto's,
  dus pas je liever alleen de map met foto's aan, niet de gegenereerde
  HTML zelf.
- Het uploadt niks naar Netlify — dat blijft een aparte stap (zie hieronder).

## Naar Netlify

Zodra `index.html` en de map `images/` klaarstaan:
1. Ga naar app.netlify.com en sleep de hele map (index.html + images/)
   naar het "Deploy"-vak op hun site.
2. Klaar — je krijgt een gratis link die je met iedereen kunt delen.
