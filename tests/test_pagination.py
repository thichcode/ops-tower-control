import unittest

from sqlalchemy import create_engine, Column, Integer, Text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.services.pagination import paginate

PaginationTestBase = declarative_base()


class PaginationItem(PaginationTestBase):
    __tablename__ = "pagination_items"
    id = Column(Integer, primary_key=True)
    name = Column(Text)


class PaginationTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        PaginationTestBase.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_paginate_returns_first_page(self):
        for i in range(5):
            self.db.add(PaginationItem(name=f"Item {i}"))
        self.db.commit()

        result = paginate(self.db.query(PaginationItem), page=1, per_page=2)

        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["pages"], 3)
        self.assertEqual(result["per_page"], 2)
        self.assertTrue(result["has_next"])
        self.assertFalse(result["has_prev"])

    def test_paginate_returns_last_page(self):
        for i in range(5):
            self.db.add(PaginationItem(name=f"Item {i}"))
        self.db.commit()

        result = paginate(self.db.query(PaginationItem), page=3, per_page=2)

        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["page"], 3)
        self.assertFalse(result["has_next"])
        self.assertTrue(result["has_prev"])

    def test_paginate_accepts_custom_per_page(self):
        for i in range(5):
            self.db.add(PaginationItem(name=f"Item {i}"))
        self.db.commit()

        result = paginate(self.db.query(PaginationItem), page=1, per_page=2)

        self.assertEqual(result["page"], 1)
        self.assertEqual(result["per_page"], 2)
        self.assertEqual(len(result["items"]), 2)

    def test_paginate_empty_query(self):
        result = paginate(self.db.query(PaginationItem), page=1, per_page=10)

        self.assertEqual(result["items"], [])
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["pages"], 0)
        self.assertFalse(result["has_next"])
        self.assertFalse(result["has_prev"])
