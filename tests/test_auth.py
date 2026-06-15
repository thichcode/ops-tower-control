import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import User


class AuthTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_hash_and_verify_password(self):
        from app.auth import hash_password, verify_password

        pw = "my-secret-password"
        hashed = hash_password(pw)

        self.assertNotEqual(hashed, pw)
        self.assertTrue(verify_password(pw, hashed))
        self.assertFalse(verify_password("wrong-password", hashed))

    def test_authenticate_user_returns_user_on_valid_credentials(self):
        from app.auth import authenticate_user, hash_password

        user = User(display_name="Test User", email="test@example.com", role="member", password_hash=hash_password("correct-pw"))
        self.db.add(user)
        self.db.commit()

        result = authenticate_user(self.db, "test@example.com", "correct-pw")
        self.assertIsNotNone(result)
        self.assertEqual(result.email, "test@example.com")

    def test_authenticate_user_returns_none_on_wrong_password(self):
        from app.auth import authenticate_user, hash_password

        user = User(display_name="Test User", email="test@example.com", role="member", password_hash=hash_password("correct-pw"))
        self.db.add(user)
        self.db.commit()

        result = authenticate_user(self.db, "test@example.com", "wrong-pw")
        self.assertIsNone(result)

    def test_authenticate_user_returns_none_on_unknown_email(self):
        from app.auth import authenticate_user, hash_password

        result = authenticate_user(self.db, "unknown@example.com", "any-pw")
        self.assertIsNone(result)

    def test_authenticate_user_returns_none_for_inactive_user(self):
        from app.auth import authenticate_user, hash_password

        user = User(display_name="Inactive", email="inactive@example.com", role="member", is_active=False, password_hash=hash_password("pw"))
        self.db.add(user)
        self.db.commit()

        result = authenticate_user(self.db, "inactive@example.com", "pw")
        self.assertIsNone(result)

    def test_role_checker_allows_correct_role(self):
        from app.auth import require_role

        admin = User(id=1, display_name="Admin", email="admin@example.com", role="admin")
        member = User(id=2, display_name="Member", email="member@example.com", role="member")

        self.assertTrue(require_role("admin", "leader")(admin))
        self.assertTrue(require_role("member")(member))
        self.assertTrue(require_role("admin", "member")(member))

    def test_role_checker_rejects_wrong_role(self):
        from app.auth import require_role

        member = User(id=1, display_name="Member", email="member@example.com", role="member")

        self.assertFalse(require_role("admin")(member))
        self.assertFalse(require_role("leader")(member))


if __name__ == "__main__":
    unittest.main()
