"""Pure receipt namespace checks; no installer or filesystem mutation."""
import json
import unittest
from scripts.installation import ownership as o

class ReservedReceiptTests(unittest.TestCase):
    def record(self, **parts):
        return dict(schema=o.SCHEMA,provider='codex',scope='project',files={},**parts)

    def test_path_rejects_case_variants_in_allowed_roots(self):
        for root in ('.codex', '.agents', '.agents/skills/lead'):
            for leaf in (o.RECEIPT_NAME, o.RECEIPT_NAME.upper(), '.Orche-Install.v1.Json'):
                with self.subTest(root=root,leaf=leaf):
                    with self.assertRaises(ValueError):o.validate_path(root+'/'+leaf,'codex','project')

    def test_serialized_files_and_directories_refuse_alias(self):
        for category in ('files','directories'):
            record=self.record();path='.codex/.ORCHE-INSTALL.V1.JSON'
            record[category]={path:'0'*64} if category=='files' else [path]
            with self.subTest(category=category):
                with self.assertRaises(ValueError):o.decode_record(json.dumps(record).encode(),'codex','project')
                with self.assertRaises(ValueError):o.serialize_record(record,'codex','project')

    def test_fresh_filter_omits_reserved_alias_without_dropping_other_files(self):
        files={'.agents/skills/lead/.ORCHE-INSTALL.V1.JSON':'0'*64,
               '.agents/skills/lead/SKILL.md':'1'*64}
        raw=o.serialize_fresh_payloads(files,'codex','project')
        self.assertEqual(o.decode_record(raw,'codex','project')['files'],
                         {'.agents/skills/lead/SKILL.md':'1'*64})
        self.assertEqual(len(files),2)

    def test_reserved_only_is_no_fresh_receipt(self):
        self.assertIsNone(o.serialize_fresh_payloads({'.agents/skills/lead/.ORCHE-INSTALL.V1.JSON':'0'*64},'codex','project'))

    def test_nonreserved_similar_leaf_still_supported(self):
        for leaf in ('.orche-install.v1.json.backup','notes.json','ORCHE-INSTALL.V1.JSON'):
            path='.agents/skills/lead/'+leaf
            self.assertEqual(o.validate_path(path,'codex','project'),path)

if __name__=='__main__':unittest.main()
