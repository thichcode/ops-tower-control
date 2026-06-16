import asyncio
import json
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import WorkItem
from app.routers.importer import import_upload


class FakeUploadFile:
    def __init__(self, filename: str, data: dict):
        self.filename = filename
        self._content = json.dumps(data).encode("utf-8")

    async def read(self) -> bytes:
        return self._content


class ImporterTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_legacy_upload_creates_requester_token(self):
        upload = FakeUploadFile("tasks.json", {"tasks": [{"title": "Legacy imported task"}]})

        with patch("app.routers.importer.TemplateResponse", side_effect=lambda name, context, **kwargs: context):
            result = asyncio.run(import_upload(object(), upload, self.db, True))

        self.assertEqual(result["result"]["imported"], 1)
        item = self.db.query(WorkItem).one()
        self.assertTrue(item.requester_token)


if __name__ == "__main__":
    unittest.main()
