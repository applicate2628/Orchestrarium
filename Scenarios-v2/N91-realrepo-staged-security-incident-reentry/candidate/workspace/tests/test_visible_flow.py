import unittest

from incidentflow import ExportRequest, ExportService


class VisibleFlowTests(unittest.TestCase):
    def test_owner_export_happy_path(self):
        service = ExportService(
            {
                "res-1": {
                    "tenant_id": "tenant-a",
                    "owner_user_id": "user-a",
                }
            },
            b"visible-secret",
        )
        result = service.create_export(
            ExportRequest(
                tenant_id="tenant-a",
                user_id="user-a",
                resource_id="res-1",
                role="owner",
                return_url="https://exports.example.com/downloads/report.csv",
                issued_at=100,
                nonce="visible-nonce",
            )
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["return_url"], "https://exports.example.com/downloads/report.csv")
        self.assertIn("token", result)


if __name__ == "__main__":
    unittest.main()
