import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0008_child_address_child_doctor_name_child_doctor_phone"),
    ]

    operations = [
        migrations.CreateModel(
            name="Contact",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ("full_name", models.CharField(max_length=160, verbose_name="F.I.O.")),
                ("relation", models.CharField(max_length=60, verbose_name="Kimligi")),
                ("phone", models.CharField(max_length=20, verbose_name="Telefon")),
                ("kind", models.CharField(choices=[
                    ("parent", "Ota-ona"), ("family", "Qarindosh"),
                    ("pickup", "Olib ketuvchi"), ("emergency", "Favqulodda")],
                    max_length=10, verbose_name="Turi")),
                ("is_primary", models.BooleanField(default=False, verbose_name="Asosiy aloqa")),
                ("is_payer", models.BooleanField(default=False, verbose_name="To'lovchi")),
                ("can_pickup", models.BooleanField(default=False, verbose_name="Olib ketishi mumkin")),
                ("has_app_access", models.BooleanField(default=False, verbose_name="Kabinetga kirish")),
                ("can_see_billing", models.BooleanField(default=False, verbose_name="Moliyani ko'rish")),
                ("receives_messages", models.BooleanField(default=True, verbose_name="Xabar oladi")),
                ("note", models.CharField(blank=True, max_length=200, verbose_name="Izoh")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("child", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="contacts", to="school.child")),
            ],
            options={"ordering": ["-is_primary", "kind", "full_name"]},
        ),
        migrations.AddIndex(
            model_name="contact",
            index=models.Index(fields=["child", "kind"], name="school_cont_child_i_2d07d0_idx"),
        ),
    ]
