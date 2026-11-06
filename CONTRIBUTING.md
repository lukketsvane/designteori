# Bidra til DESIGNTEORI

Alle kan føreslå nye kjelder og feilrettingar i ein pull request. Oppgje DOI eller annan permanent identifikator, originalkjelde, tittel, forfattarar, år og korleis nordisk tilknyting er dokumentert. Merkte kandidatar skal ikkje forvekslast med verifiserte verk.

Eit open-access-merke gjev ikkje automatisk rett til å republisere PDF-ar. For offentleg spegling krevst lisens for den konkrete PDF-versjonen, originalkjelde, SHA-256 og verifikasjonsdato. Andre opne dokument blir lenkja eller lagra i privat cache.

## Lokal utvikling

Installer avhengnader med python -m pip install -r requirements.txt. På PowerShell set du miljøvariabelen PYTHONPATH=scripts og køyrer python -m unittest discover -s tests -p test_*.py -v, deretter python tests/test_database.py. Den offentlege katalogen ligg i docs/ og kjelde- og rettsreglane i fulltekst/INNSAMLING.md.

Automatiske klassifiseringar er ikkje menneskeleg kvalitetssikring. Dokumenter uvisse, negative funn og eventuelle DOI-dublettar, og legg ved grunngjeving for alle samanslåingar.
