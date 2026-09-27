from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("operations", "0004_serviceheartbeat"),
        ("school", "0020_childdocument"),
    ]

    operations = [
        migrations.AddField(
            model_name="announcement",
            name="audience",
            field=models.CharField(
                choices=[
                    ("all", "Barcha ota-onalar"),
                    ("group", "Ma'lum guruh"),
                    ("debtors", "Faqat qarzdorlar"),
                ],
                default="all",
                max_length=12,
                verbose_name="Auditoriya",
            ),
        ),
        migrations.AddField(
            model_name="announcement",
            name="group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="announcements",
                to="school.group",
                verbose_name="Guruh",
            ),
        ),
    ]
