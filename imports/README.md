# Import av nordiske publikasjonar

Legg **berre bibliografiske metadata** (ikkje fulltekst eller verna samandrag) i `imports/<kjelde>/`. Støtta format: CSV, JSON, JSONL, RIS og OAI-PMH/XML. GitHub Actions importerer og avstemmer filene automatisk ved neste push.

Kjeldemapper: `nva` (Noreg), `diva` og `chalmers` (Sverige), `aalto` (Finland), `kgl` (Danmark), `iris` og `skemman` (Island), `nordes` og `cephad`.

Lokal bruk: `python import_norden.py --source nva --input eksport.csv`, deretter `python samkoyr_norden.py`.

**Prinsipp:** DOI eller eksakt OpenAlex-ID kan gje sikker identitetskopling; samanfallande tittel/år gir berre kontrollbehov. Kjeldeland er ikkje automatisk forfattarens institusjonstilknyting. Nye metadata blir merkte uavklara fram til fagleg gjennomgang. Ingen importerte postar blir automatisk rekna som verifiserte designteoriartiklar.
