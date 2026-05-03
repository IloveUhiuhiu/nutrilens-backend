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
        if not self.id:
            self.id = f"daily_{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Log {self.date} - {self.user.username}"

class MealEntry(models.Model):
    """Một bữa ăn cụ thể """
    id = models.CharField(
        primary_key=True, 
        max_length=20, 
        editable=False, 
        unique=True)
    log = models.ForeignKey(DailyLog, on_delete=models.CASCADE, related_name='meals')
    food = models.ForeignKey('nutrients.Food', on_delete=models.SET_NULL, null=True, blank=True)
    
    meal_time = models.DateTimeField(auto_now_add=True)
    image_path = models.ImageField(upload_to='meal_images/', verbose_name="Ảnh gốc RGB")
    source_type = models.CharField(max_length=50, default="camera")
    
    total_calories = models.FloatField(default=0)
    total_protein = models.FloatField(default=0)
    total_carbs = models.FloatField(default=0)
    total_fat = models.FloatField(default=0)
    total_weight = models.FloatField(default=0)

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f"meal_{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)

    def __str__(self):
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
    mask_path = models.ImageField(upload_to='masks/', verbose_name="Ảnh Mask")
    
    volume = models.FloatField(verbose_name="Thể tích (cm3)") 
    calculated_weight = models.FloatField(verbose_name="Khối lượng tính toán (g)", editable=False)

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f"comp_{uuid.uuid4().hex[:8]}"
        
        # Logic tính toán khối lượng: m = V * density
        if self.volume and self.physical_data:
            self.calculated_weight = self.volume * self.physical_data.density
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.component_name} ({self.calculated_weight}g)"