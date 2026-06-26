"""
Consistent error envelope (§9.1).

    {
      "error": {
        "code": "VALIDATION_ERROR",
        "message": "Title is required.",
        "details": {"title": ["This field is required."]}
      }
    }

A custom DRF exception handler reshapes every framework error into this shape.
Views that need a domain-specific code (e.g. 409 ALREADY_CLAIMED) raise
``ApiError`` directly.
"""
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler

# Map common HTTP statuses to the documented machine codes.
_STATUS_CODES = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    429: "RATE_LIMITED",
}


class ApiError(APIException):
    """Raise to emit a specific code/message, e.g. ``ApiError('ALREADY_CLAIMED', ...)``."""

    def __init__(self, code, message, status_code=status.HTTP_400_BAD_REQUEST, details=None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(detail=message)


def envelope_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    code = getattr(exc, "code", None) or _STATUS_CODES.get(response.status_code, "ERROR")
    details = getattr(exc, "details", None)
    data = response.data

    if isinstance(exc, ApiError):
        message = exc.message
    elif isinstance(data, dict) and "detail" in data and len(data) == 1:
        message = str(data["detail"])
    elif isinstance(data, dict):
        # Field-level validation errors → details, with a human summary message.
        details = details or data
        first = next(iter(data.values()), None)
        if isinstance(first, (list, tuple)) and first:
            message = str(first[0])
        else:
            message = "Request could not be processed."
    elif isinstance(data, list) and data:
        message = str(data[0])
    else:
        message = "Request could not be processed."

    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
