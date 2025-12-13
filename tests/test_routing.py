from secure_proxy_gateway.proxy.engine import match_route
from secure_proxy_gateway.core.models import RequestRules, ResponseRules, RouteConfig


def test_match_route_longest_prefix():
    routes = [
        RouteConfig(
            name="short",
            path="/api",
            target="https://example.com",
            request_rules=RequestRules(),
            response_rules=ResponseRules(),
        ),
        RouteConfig(
            name="long",
            path="/api/users",
            target="https://example.com",
            request_rules=RequestRules(),
            response_rules=ResponseRules(),
        ),
    ]
    matched, has_path_match = match_route("/api/users/123", "GET", routes)
    assert has_path_match is True
    assert matched is not None
    assert matched.name == "long"


def test_match_route_method_filter():
    routes = [
        RouteConfig(
            name="orders",
            path="/api/orders",
            target="https://example.com",
            method="GET",
            request_rules=RequestRules(),
            response_rules=ResponseRules(),
        )
    ]
    matched, has_path_match = match_route("/api/orders", "POST", routes)
    assert has_path_match is True
    assert matched is None

    matched, has_path_match = match_route("/api/orders", "GET", routes)
    assert has_path_match is True
    assert matched is not None
    assert matched.name == "orders"
