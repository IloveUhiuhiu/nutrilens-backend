from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0002_mealcomponent_calories_mealcomponent_carbs_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mealentry',
            name='image_path',
            field=models.URLField(blank=True, max_length=500, null=True, verbose_name='URL Ảnh gốc'),
        ),
        migrations.AlterField(
            model_name='mealcomponent',
            name='mask_path',
            field=models.URLField(blank=True, max_length=500, null=True, verbose_name='URL Ảnh Mask'),
        ),
    ]
