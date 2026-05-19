# Generated manually for account profile, OTP purpose, and quota APIs.

import accounts.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_remove_user_first_name_remove_user_last_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='accountotp',
            name='purpose',
            field=models.CharField(
                choices=[
                    ('account_verify', 'Account verification'),
                    ('password_reset', 'Password reset'),
                ],
                default='account_verify',
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='goal',
            field=models.CharField(
                choices=[
                    ('maintain', 'Maintain weight'),
                    ('lose_weight', 'Lose weight'),
                    ('gain_weight', 'Gain weight'),
                ],
                default='maintain',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='phone_number',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='tdee',
            field=models.FloatField(default=0, help_text='Total Daily Energy Expenditure'),
        ),
        migrations.CreateModel(
            name='QuotaConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(default='guest_scan_limit', max_length=50, unique=True)),
                ('guest_scan_limit', models.PositiveIntegerField(default=2)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AlterModelManagers(
            name='user',
            managers=[
                ('objects', accounts.models.UserManager()),
            ],
        ),
    ]
