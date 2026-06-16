import unittest

from app.main import app


class RouteSecurityTest(unittest.TestCase):
    def test_core_mutation_routes_require_auth_dependency(self):
        protected_routes = {
            ("POST", "/work-items"),
            ("POST", "/work-items/{item_id}/done"),
            ("POST", "/work-items/{item_id}/blocked"),
            ("POST", "/work-items/{item_id}/edit"),
            ("POST", "/capacity/{user_id}"),
            ("POST", "/services"),
            ("POST", "/services/{service_id}/delete"),
            ("POST", "/services/{service_id}/activate"),
            ("POST", "/users"),
            ("POST", "/users/{user_id}/delete"),
            ("POST", "/users/{user_id}/activate"),
            ("POST", "/import/upload"),
            ("POST", "/api/intake/sdp"),
            ("POST", "/api/intake/zabbix"),
            ("POST", "/api/intake/digest"),
            ("POST", "/api/intake/alerts"),
            ("POST", "/api/intake/retention"),
        }

        missing = []
        for route in app.routes:
            if not hasattr(route, "methods"):
                continue
            for method in route.methods:
                key = (method, route.path)
                if key in protected_routes and not _has_auth_dependency(route):
                    missing.append(f"{method} {route.path}")

        self.assertEqual(missing, [])


def _has_auth_dependency(route) -> bool:
    for dependency in route.dependant.dependencies:
        call = dependency.call
        if getattr(call, "__module__", "") == "app.auth":
            return True
    return False


if __name__ == "__main__":
    unittest.main()
