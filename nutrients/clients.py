import requests
from django.conf import settings
from rest_framework import status


class ExternalLookupError(Exception):
    """Chức năng: biểu diễn lỗi gọi API ngoài. Đầu vào: message/code/status. Đầu ra: exception chuẩn."""

    def __init__(self, message, code="external_api_error", status_code=status.HTTP_502_BAD_GATEWAY):
        self.public_message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class BaseExternalClient:
    """Chức năng: client nền cho API ngoài. Đầu vào: base_url/timeout. Đầu ra: JSON hoặc lỗi chuẩn."""

    service_name = "external_api"

    def __init__(self, base_url, timeout):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get(self, path, *, params=None, headers=None):
        """Chức năng: gọi GET API ngoài. Đầu vào: path, params, headers. Đầu ra: JSON payload."""
        url = f"{self.base_url}{path}"
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.Timeout as exc:
            raise ExternalLookupError(
                f"{self.service_name} request timed out.",
                code="timeout",
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            ) from exc
        except requests.HTTPError as exc:
            response = exc.response
            if response is not None and response.status_code == status.HTTP_404_NOT_FOUND:
                raise ExternalLookupError(
                    f"{self.service_name} resource not found.",
                    code="not_found",
                    status_code=status.HTTP_404_NOT_FOUND,
                ) from exc
            raise ExternalLookupError(
                f"{self.service_name} returned an error.",
                code="bad_gateway",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc
        except requests.RequestException as exc:
            raise ExternalLookupError(
                f"{self.service_name} is unavailable.",
                code="unavailable",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc
        except ValueError as exc:
            raise ExternalLookupError(
                f"{self.service_name} returned invalid JSON.",
                code="invalid_json",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc


class OpenFoodFactsClient(BaseExternalClient):
    """Chức năng: client OpenFoodFacts. Đầu vào: settings. Đầu ra: payload sản phẩm barcode."""

    service_name = "open_food_facts"

    def __init__(self):
        super().__init__(settings.OPEN_FOOD_FACTS_BASE_URL, settings.EXTERNAL_API_TIMEOUT)
        self.user_agent = settings.OPEN_FOOD_FACTS_USER_AGENT

    def lookup_barcode(self, barcode):
        """Chức năng: tra barcode trên OpenFoodFacts. Đầu vào: barcode. Đầu ra: payload hoặc None."""
        payload = self.get(
            f"/api/v2/product/{barcode}.json",
            headers={"User-Agent": self.user_agent},
        )
        if payload.get("status") != 1 or not payload.get("product"):
            return None
        return payload


class USDAClient(BaseExternalClient):
    """Chức năng: client USDA FoodData Central. Đầu vào: settings. Đầu ra: payload USDA."""

    service_name = "usda"

    def __init__(self):
        super().__init__(settings.USDA_BASE_URL, settings.EXTERNAL_API_TIMEOUT)
        self.api_key = settings.USDA_API_KEY

    def _require_api_key(self):
        """Chức năng: kiểm tra API key. Đầu vào: không có. Đầu ra: None hoặc lỗi chuẩn."""
        if not self.api_key:
            raise ExternalLookupError(
                "USDA_API_KEY is not configured.",
                code="missing_config",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    def search_foods(self, query, page_size=20, page_number=1):
        """Chức năng: tìm món trên USDA. Đầu vào: query, page size/page number. Đầu ra: payload search."""
        self._require_api_key()
        return self.get(
            "/foods/search",
            params={
                "api_key": self.api_key,
                "query": query,
                "pageSize": page_size,
                "pageNumber": page_number,
            },
        )

    def get_food(self, fdc_id):
        """Chức năng: lấy chi tiết món USDA. Đầu vào: fdc_id. Đầu ra: payload detail."""
        self._require_api_key()
        return self.get(f"/food/{fdc_id}", params={"api_key": self.api_key})
