from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("operations", "0003_alter_cashshift_actual_balance_and_more")]
    operations = [migrations.CreateModel(name="ServiceHeartbeat", fields=[
        ("service", models.CharField(max_length=40, primary_key=True, serialize=False)),
        ("seen_at", models.DateTimeField()),
        ("details", models.JSONField(blank=True, default=dict)),
    ])]
