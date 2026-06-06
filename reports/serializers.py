from rest_framework import serializers


class DateRangeQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField(required=True)
    date_to = serializers.DateField(required=True)

    def to_internal_value(self, data):
        """Chức năng: map query params from/to. Đầu vào: query params. Đầu ra: validated data."""
        return super().to_internal_value({"date_from": data.get("from"), "date_to": data.get("to")})


class OptionalDateRangeQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def to_internal_value(self, data):
        """Chức năng: map query params from/to tùy chọn. Đầu vào: query params. Đầu ra: validated data."""
        mapped = {}
        if data.get("from"):
            mapped["date_from"] = data.get("from")
        if data.get("to"):
            mapped["date_to"] = data.get("to")
        return super().to_internal_value(mapped)


class AdviceDateQuerySerializer(serializers.Serializer):
    date = serializers.DateField(required=False)
