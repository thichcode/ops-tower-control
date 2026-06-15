import unittest

from starlette.requests import Request

from app.templates import TemplateResponse, templates


class TemplateResponseTest(unittest.TestCase):
    def test_all_templates_compile(self):
        for name in templates.env.list_templates():
            with self.subTest(template=name):
                templates.get_template(name)

    def test_supports_existing_router_call_style(self):
        request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})

        response = TemplateResponse("users.html", {"request": request, "users": []})

        self.assertEqual(response.status_code, 200)
        self.assertIn("User Management", response.body.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
