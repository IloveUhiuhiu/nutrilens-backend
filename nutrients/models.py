import uuid
from django.db import models

class IngredientPhysicalData(models.Model):
    """Lưu trữ khối lượng riêng và thông số dinh dưỡng chuẩn của nguyên liệu"""
    id = models.CharField(
        primary_key=True, 
        max_length=20, 
        editable=False, 
        unique=True)
    vi_name = models.CharField(max_length=255, verbose_name="Tên tiếng Việt")
    en_name = models.CharField(max_length=255, verbose_name="Tên tiếng Anh")
    density = models.FloatField(help_text="Khối lượng riêng (g/cm3)")
    cal_per_100g = models.FloatField(verbose_name="Calories/100g")
    fat_per_100g = models.FloatField(verbose_name="Fat/100g")
    carb_per_100g = models.FloatField(verbose_name="Carb/100g")
    protein_per_100g = models.FloatField(verbose_name="Protein/100g")
    image_url = models.URLField(max_length=500, blank=True, null=True)
    fdc_id_ref = models.CharField(max_length=50, blank=True, null=True, help_text="Mã tham chiếu USDA")

    def save(self, *args, **kwargs):
        """Chức năng: lưu nguyên liệu và sinh id. Đầu vào: args/kwargs save. Đầu ra: Ingredient được lưu."""
        if not self.id:
            self.id = f"igr_{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)

    def __str__(self):
        """Chức năng: biểu diễn nguyên liệu. Đầu vào: instance. Đầu ra: tên và density."""
        return f"{self.vi_name} ({self.density} g/cm3)"

class Food(models.Model):
    """Danh mục các món ăn hoàn chỉnh"""
    id = models.CharField(
        primary_key=True, 
        max_length=20, 
        editable=False, 
        unique=True)
    vi_name = models.CharField(max_length=255, verbose_name="Tên tiếng Việt")
    en_name = models.CharField(max_length=255, verbose_name="Tên tiếng Anh")
    fdc_id = models.CharField(max_length=50, unique=True, help_text="Mã tham chiếu USDA")
    category = models.CharField(max_length=100)
    image_url = models.URLField(max_length=500, blank=True, null=True)
    external_source = models.CharField(max_length=50, default="usda")
    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        """Chức năng: lưu món ăn và sinh id. Đầu vào: args/kwargs save. Đầu ra: Food được lưu."""
        if not self.id:
            self.id = f"food_{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)

    def __str__(self):
        """Chức năng: biểu diễn món ăn. Đầu vào: instance. Đầu ra: tên tiếng Việt."""
        return self.vi_name

class PackagedFood(models.Model):
    """Thực phẩm đóng gói dùng cho tra cứu barcode"""
    id = models.CharField(
        primary_key=True,
        max_length=20,
        editable=False,
        unique=True)
    barcode = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=255, blank=True, null=True)
    serving_size = models.FloatField(default=100)
    serving_unit = models.CharField(max_length=50, default="g")
    cal_per_serving = models.FloatField(default=0)
    fat_per_serving = models.FloatField(default=0)
    carb_per_serving = models.FloatField(default=0)
    protein_per_serving = models.FloatField(default=0)
    image_url = models.URLField(max_length=500, blank=True, null=True)
    external_source = models.CharField(max_length=50, default="open_food_facts")
    external_id = models.CharField(max_length=100, blank=True, null=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        """Chức năng: lưu packaged food và sinh id. Đầu vào: args/kwargs save. Đầu ra: PackagedFood được lưu."""
        if not self.id:
            self.id = f"pkg_{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)

    def __str__(self):
        """Chức năng: biểu diễn packaged food. Đầu vào: instance. Đầu ra: tên và barcode."""
        return f"{self.name} ({self.barcode})"
        
class HealthAdviceRule(models.Model):
    """Quy tắc đưa ra lời khuyên dựa trên % TDEE nạp vào"""
    LEVEL_CHOICES = [
        ('normal', 'Normal'),
        ('warning', 'Warning'),
        ('danger', 'Danger'),
    ]
    min_percent = models.FloatField(help_text="Ngưỡng % TDEE tối thiểu")
    max_percent = models.FloatField(help_text="Ngưỡng % TDEE tối đa")
    alert_level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    advice_content = models.TextField()

    def __str__(self):
        """Chức năng: biểu diễn rule tư vấn. Đầu vào: instance. Đầu ra: mức cảnh báo và ngưỡng."""
        return f"Rule {self.alert_level}: {self.min_percent}% - {self.max_percent}%"
