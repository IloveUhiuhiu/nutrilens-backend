import uuid
from django.db import models
from django.conf import settings

class DailyLog(models.Model):
    """Tổng hợp dinh dưỡng theo ngày cho người dùng"""
    id = models.CharField(
        primary_key=True, 
        max_length=20, 
        editable=False, 
        unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='daily_logs')
    date = models.DateField(verbose_name="Ngày ghi chép")
    
    total_calories = models.FloatField(default=0)
    total_protein = models.FloatField(default=0)
    total_carbs = models.FloatField(default=0)
    total_fat = models.FloatField(default=0)
    total_weight = models.FloatField(default=0)

    def save(self, *args, **kwargs):
        """Chức năng: lưu daily log và sinh id. Đầu vào: args/kwargs save. Đầu ra: DailyLog được lưu."""
        if not self.id:
            self.id = f"daily_{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)

    def __str__(self):
        """Chức năng: biểu diễn daily log. Đầu vào: instance. Đầu ra: ngày và email user."""
        return f"Log {self.date} - {self.user.email}"

class MealEntry(models.Model):
    """Một bữa ăn cụ thể """
    SOURCE_CHOICES = [
        ('image', 'Image'),
        ('barcode', 'Barcode'),
        ('text', 'Text'),
        ('voice', 'Voice'),
        ('manual', 'Manual'),
    ]

    id = models.CharField(
        primary_key=True, 
        max_length=20, 
        editable=False, 
        unique=True)
    log = models.ForeignKey(DailyLog, on_delete=models.CASCADE, related_name='meals')
    food = models.ForeignKey('nutrients.Food', on_delete=models.SET_NULL, null=True, blank=True)
    packaged_food = models.ForeignKey('nutrients.PackagedFood', on_delete=models.SET_NULL, null=True, blank=True)
    
    meal_time = models.DateTimeField(auto_now_add=True)
    image_path = models.ImageField(upload_to='meal_images/', verbose_name="Ảnh gốc RGB", null=True, blank=True)
    source_type = models.CharField(max_length=50, choices=SOURCE_CHOICES, default="image")
    barcode = models.CharField(max_length=64, blank=True, null=True)
    search_query = models.CharField(max_length=255, blank=True, null=True)
    inference_job_id = models.CharField(max_length=20, blank=True, null=True)
    serving_amount = models.FloatField(null=True, blank=True)
    serving_unit_id = models.CharField(max_length=100, blank=True, null=True)
    serving_unit_label = models.CharField(max_length=255, blank=True, null=True)
    is_confirmed = models.BooleanField(default=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    total_calories = models.FloatField(default=0)
    total_protein = models.FloatField(default=0)
    total_carbs = models.FloatField(default=0)
    total_fat = models.FloatField(default=0)
    total_weight = models.FloatField(default=0)

    def save(self, *args, **kwargs):
        """Chức năng: lưu meal entry và sinh id. Đầu vào: args/kwargs save. Đầu ra: MealEntry được lưu."""
        if not self.id:
            self.id = f"meal_{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)

    def __str__(self):
        """Chức năng: biểu diễn meal. Đầu vào: instance. Đầu ra: id và thời gian meal."""
        return f"Meal {self.id} tại {self.meal_time.strftime('%H:%M %d/%m')}"

class MealComponent(models.Model):
    """Thành phần chi tiết được bóc tách từ AI"""
    id = models.CharField(
        primary_key=True, 
        max_length=20, 
        editable=False, 
        unique=True)
    meal_entry = models.ForeignKey(MealEntry, on_delete=models.CASCADE, related_name='components')
    physical_data = models.ForeignKey('nutrients.IngredientPhysicalData', on_delete=models.PROTECT)
    
    component_name = models.CharField(max_length=255, verbose_name="Tên thành phần")
    mask_path = models.ImageField(upload_to='masks/', verbose_name="Ảnh Mask", null=True, blank=True)
    
    volume = models.FloatField(verbose_name="Thể tích (cm3)") 
    calculated_weight = models.FloatField(verbose_name="Khối lượng tính toán (g)", editable=False)
    calories = models.FloatField(default=0)
    protein = models.FloatField(default=0)
    carbs = models.FloatField(default=0)
    fat = models.FloatField(default=0)

    def save(self, *args, **kwargs):
        """Chức năng: lưu component, chỉ tự tính macro nếu chưa có dữ liệu AI. Đầu vào: volume/physical_data/macro. Đầu ra: MealComponent."""
        if not self.id:
            self.id = f"comp_{uuid.uuid4().hex[:8]}"
        
        has_ai_macro = any([self.calculated_weight, self.calories, self.protein, self.carbs, self.fat])
        if self.volume and self.physical_data and not has_ai_macro:
            self.calculated_weight = self.volume * self.physical_data.density
            self.calories = self.calculated_weight * self.physical_data.cal_per_100g / 100
            self.protein = self.calculated_weight * self.physical_data.protein_per_100g / 100
            self.carbs = self.calculated_weight * self.physical_data.carb_per_100g / 100
            self.fat = self.calculated_weight * self.physical_data.fat_per_100g / 100
            
        super().save(*args, **kwargs)

    def __str__(self):
        """Chức năng: biểu diễn component. Đầu vào: instance. Đầu ra: tên và cân nặng tính toán."""
        return f"{self.component_name} ({self.calculated_weight}g)"
