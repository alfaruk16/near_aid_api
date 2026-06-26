from rest_framework.pagination import CursorPagination
from rest_framework.response import Response


class CursorEnvelopePagination(CursorPagination):
    """Cursor pagination emitting the §9.1 envelope.

    ``{"results": [...], "next_cursor": "eyJ...", "has_more": true}``

    Cursor pagination (rather than offset) keeps feeds stable as new listings
    arrive and avoids deep-offset cost on the geospatial queries.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-created_at"
    cursor_query_param = "cursor"

    def get_paginated_response(self, data):
        next_link = self.get_next_link()
        next_cursor = None
        if next_link:
            from urllib.parse import parse_qs, urlparse

            qs = parse_qs(urlparse(next_link).query)
            values = qs.get(self.cursor_query_param)
            next_cursor = values[0] if values else None
        return Response(
            {
                "results": data,
                "next_cursor": next_cursor,
                "has_more": next_cursor is not None,
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "results": schema,
                "next_cursor": {"type": "string", "nullable": True},
                "has_more": {"type": "boolean"},
            },
        }
