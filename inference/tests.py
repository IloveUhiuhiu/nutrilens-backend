from django.test import TestCase

from nutrients.models import IngredientPhysicalData

from .serializers import InferenceJobCreateSerializer
from .services import normalize_ai_result


class InferenceJobCreateSerializerTests(TestCase):
    def test_mobile_intrinsics_metadata_does_not_require_camera_height(self):
        serializer = InferenceJobCreateSerializer()

        metadata = serializer.validate_camera_metadata(
            {
                "width": 3024,
                "height": 4032,
                "fx": 2685.2,
                "fy": 2688.4,
                "cx": 1512,
                "cy": 2016,
            }
        )

        self.assertEqual(metadata["camera_width"], 3024)
        self.assertEqual(metadata["camera_height"], 4032)
        self.assertEqual(metadata["camera_area"], 3024 * 4032)
        self.assertEqual(metadata["intrinsics"]["fx"], 2685.2)
        self.assertEqual(metadata["intrinsics"]["fy"], 2688.4)


class NormalizeAIResultNutritionTests(TestCase):
    def test_backend_calculates_nutrition_from_ai_geometry(self):
        IngredientPhysicalData.objects.create(
            id="igr_rice",
            vi_name="Cơm trắng",
            en_name="white rice",
            density=1.3,
            cal_per_100g=130,
            fat_per_100g=0.3,
            carb_per_100g=28,
            protein_per_100g=2.7,
            fdc_id_ref="fdc_rice",
        )

        result = normalize_ai_result(
            {
                "model_version": "seg-nutrition-v1",
                "latency_ms": 123,
                "components": [
                    {
                        "component_id": "comp_001",
                        "component_name": "boiled white rice",
                        "mask_path": "masks/comp_001.png",
                        "volume": 100,
                    }
                ],
            }
        )

        self.assertEqual(result["total_weight"], 130)
        self.assertEqual(result["total_calories"], 169)
        self.assertEqual(result["total_protein"], 3.51)
        self.assertEqual(result["total_carbs"], 36.4)
        self.assertEqual(result["total_fat"], 0.39)
        self.assertEqual(result["components"][0]["physical_data_id"], "igr_rice")
