from django.db import migrations


def seed_categories(apps, schema_editor):
    Kindergarten = apps.get_model("school", "Kindergarten")
    Category = apps.get_model("operations", "ExpenseCategory")
    defaults = [
        ("Oziq-ovqat", "food"), ("Ijara", "rent"),
        ("Kommunal to'lovlar", "utilities"), ("Xo'jalik xarajatlari", "household"),
        ("Ta'lim materiallari", "education"), ("Boshqa xarajatlar", "other"),
    ]
    for kg in Kindergarten.objects.all():
        for name, kind in defaults:
            Category.objects.get_or_create(kindergarten=kg, name=name,
                                           defaults={"kind": kind, "is_active": True})


class Migration(migrations.Migration):
    dependencies = [("operations", "0001_initial")]
    operations = [migrations.RunPython(seed_categories, migrations.RunPython.noop)]
