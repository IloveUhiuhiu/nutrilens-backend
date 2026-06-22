from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from nutrients.models import Food, PackagedFood

from .models import DailyLog, MealEntry
from .services import recalculate_meal_quantity


def _make_user(email):
    return User.objects.create_user(email=email, password="StrongPass123")


class RecalculateMealQuantityTests(TestCase):
    def test_barcode_meal_scales_with_new_servings(self):
        packaged_food = PackagedFood.objects.create(
            id="pkg_test",
            barcode="0000000000001",
            name="Sữa chua",
            serving_size=100,
            serving_unit="g",
            cal_per_serving=90,
            protein_per_serving=4,
            carb_per_serving=12,
            fat_per_serving=2,
        )
        log = DailyLog.objects.create(user=_make_user("barcode@test.com"), date="2026-06-01")
        meal = MealEntry.objects.create(
            log=log,
            packaged_food=packaged_food,
            source_type="barcode",
            serving_amount=1,
            total_calories=90,
            total_protein=4,
            total_carbs=12,
            total_fat=2,
            total_weight=100,
        )

        changed = recalculate_meal_quantity(meal, 2)

        self.assertTrue(changed)
        self.assertEqual(meal.serving_amount, 2)
        self.assertEqual(meal.total_calories, 180)
        self.assertEqual(meal.total_protein, 8)
        self.assertEqual(meal.total_carbs, 24)
        self.assertEqual(meal.total_fat, 4)
        self.assertEqual(meal.total_weight, 200)

    def test_usda_meal_scales_with_new_grams(self):
        food = Food.objects.create(
            id="food_test",
            vi_name="Cơm trắng",
            en_name="white rice",
            fdc_id="fdc_rice",
            category="grain",
            raw_payload={
                "foodNutrients": [
                    {"nutrient": {"name": "Energy"}, "unitName": "KCAL", "amount": 130},
                    {"nutrient": {"name": "Protein"}, "amount": 2.7},
                    {"nutrient": {"name": "Carbohydrate, by difference"}, "amount": 28},
                    {"nutrient": {"name": "Total lipid (fat)"}, "amount": 0.3},
                ]
            },
        )
        log = DailyLog.objects.create(user=_make_user("usda@test.com"), date="2026-06-01")
        meal = MealEntry.objects.create(
            log=log,
            food=food,
            source_type="text",
            serving_amount=100,
            total_calories=130,
            total_protein=2.7,
            total_carbs=28,
            total_fat=0.3,
            total_weight=100,
        )

        changed = recalculate_meal_quantity(meal, 200)

        self.assertTrue(changed)
        self.assertEqual(meal.serving_amount, 200)
        self.assertEqual(meal.total_calories, 260)
        self.assertEqual(meal.total_weight, 200)

    def test_manual_meal_is_not_recalculated(self):
        log = DailyLog.objects.create(user=_make_user("manual@test.com"), date="2026-06-01")
        meal = MealEntry.objects.create(
            log=log,
            source_type="manual",
            total_calories=500,
        )

        changed = recalculate_meal_quantity(meal, 2)

        self.assertFalse(changed)
        self.assertEqual(meal.total_calories, 500)


class MealDetailViewTests(TestCase):
    def setUp(self):
        self.owner = _make_user("owner@test.com")
        self.other_user = _make_user("other@test.com")
        self.packaged_food = PackagedFood.objects.create(
            id="pkg_view_test",
            barcode="0000000000002",
            name="Sữa chua",
            serving_size=100,
            serving_unit="g",
            cal_per_serving=90,
            protein_per_serving=4,
            carb_per_serving=12,
            fat_per_serving=2,
        )
        self.log = DailyLog.objects.create(user=self.owner, date="2026-06-01")
        self.meal = MealEntry.objects.create(
            log=self.log,
            packaged_food=self.packaged_food,
            source_type="barcode",
            serving_amount=1,
            total_calories=90,
            total_protein=4,
            total_carbs=12,
            total_fat=2,
            total_weight=100,
        )
        self.client = APIClient()

    def _authenticate(self, user):
        user.is_superuser = True
        user.save(update_fields=["is_superuser"])
        self.client.force_authenticate(user=user)

    def test_patch_serving_amount_recalculates_totals_and_daily_log(self):
        self._authenticate(self.owner)

        response = self.client.patch(
            f"/api/v1/analysis/meals/{self.meal.id}/",
            {"serving_amount": 3},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.total_calories, 270)
        self.log.refresh_from_db()
        self.assertEqual(self.log.total_calories, 270)

    def test_patch_notes_only_does_not_touch_totals(self):
        self._authenticate(self.owner)

        response = self.client.patch(
            f"/api/v1/analysis/meals/{self.meal.id}/",
            {"notes": "ăn kèm trái cây"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.notes, "ăn kèm trái cây")
        self.assertEqual(self.meal.total_calories, 90)

    def test_delete_removes_meal_and_refreshes_daily_log(self):
        self._authenticate(self.owner)

        response = self.client.delete(f"/api/v1/analysis/meals/{self.meal.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(MealEntry.objects.filter(id=self.meal.id).exists())
        self.log.refresh_from_db()
        self.assertEqual(self.log.total_calories, 0)

    def test_other_user_cannot_patch_or_delete(self):
        self._authenticate(self.other_user)

        patch_response = self.client.patch(
            f"/api/v1/analysis/meals/{self.meal.id}/",
            {"serving_amount": 5},
            format="json",
        )
        delete_response = self.client.delete(f"/api/v1/analysis/meals/{self.meal.id}/")

        self.assertEqual(patch_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.total_calories, 90)
