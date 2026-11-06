"""Kontroller kopla CSV, kjelde-ID-ar og revisjonskø utan nettverk."""
import unittest
from eksporter_korpus import consolidated, safe_cell
from lag_identitetsko import make_queue


class CorpusExportTests(unittest.TestCase):
    def test_three_source_layers_not_promoted(self):
        base = [dict(id="W1",title="OpenAlex publication",year=2010,
                     kind="article",scope="automatic-title-inclusion")]
        nordic = [dict(id="nordic:1",title="Nordic research",year=2020,
                       kind="editorial-candidate",scope="editorial-candidate")]
        hist = [dict(id="theory:1",title="Classic reference",year=1950,
                     kind="book",scope="historical-reference",countries=[])]
        rows=consolidated(base,nordic,hist)
        self.assertEqual(len(rows),3)
        self.assertEqual([r["source_layer"] for r in rows],
            ["openalex","nordic-candidate","historical-candidate"])
        self.assertEqual(rows[2]["status"],"historical-reference")
        self.assertEqual(rows[0]["year"],2010)
        self.assertTrue(safe_cell("=4+4").startswith("'"))
        with self.assertRaises(ValueError):
            consolidated(base,[],[dict(id="W1",scope="historical-reference")])
        with self.assertRaises(ValueError):
            consolidated([],[],[dict(id="theory:2",scope="accepted")])

    def test_audit_tasks_are_unreviewed(self):
        nordic=[dict(id="editorial:1",title="Nordic work",status="matched-id",
                     matched_openalex_id="W1",doi="")]
        historical=[dict(source="grunnlaust",bibtex_key="simon1969",
                         title="The Sciences of the Artificial",status="candidate-new",
                         candidate_id="theory:1")]
        doi_groups=[{"doi":"10.1234/shared",
                     "records":[{"id":"W2"},{"id":"W3"}]}]
        queue=make_queue(nordic,historical,doi_groups)
        self.assertEqual(len(queue),3)
        self.assertTrue(all(r["decision"]=="UNREVIEWED" for r in queue))
        self.assertEqual(sum(r["priority"]=="high" for r in queue),2)
        self.assertEqual(queue[0]["source_layer"],"nordic")


if __name__ == "__main__":
    unittest.main()
