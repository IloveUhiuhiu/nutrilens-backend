from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Chức năng: chuẩn hóa exception DRF. Đầu vào: exception và context. Đầu ra: response envelope hoặc None."""
    response = exception_handler(exc, context)
    if response is None:
        return response

    detail = response.data
    message = "Request failed."

    if isinstance(detail, dict):
        raw_message = detail.get("detail")
        if raw_message:
            message = str(raw_message)
    elif isinstance(detail, list) and detail:
        message = str(detail[0])

    response.data = {
        "status_code": response.status_code,
        "message": message,
        "data": None,
        "errors": detail,
    }
    return response
