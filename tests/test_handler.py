import json, os, sys, unittest
from unittest.mock import MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.modules["boto3"] = MagicMock()
import handler

class HandlerTests(unittest.TestCase):
    def setUp(self): handler.table = MagicMock()
    def test_rejects_missing_fields(self):
        self.assertEqual(handler.create_incident({"body": json.dumps({"title": "Down"})})["statusCode"], 400)
    def test_creates_valid_incident(self):
        result = handler.create_incident({"body": json.dumps({"title": "Latency", "severity": "sev2", "service": "api"})})
        self.assertEqual(result["statusCode"], 201)
        self.assertEqual(json.loads(result["body"])["severity"], "SEV2")
    def test_returns_not_found(self):
        handler.table.get_item.return_value = {}
        self.assertEqual(handler.get_incident("missing")["statusCode"], 404)

if __name__ == "__main__": unittest.main()
