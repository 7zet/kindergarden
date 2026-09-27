import apps.school.models
import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_alter_user_role"), ("school", "0019_person_contactchild")]
    operations = [migrations.CreateModel(name="ChildDocument", fields=[
        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
        ("type", models.CharField(choices=[("contract", "Shartnoma skani"), ("birth", "Tug'ilganlik guvohnomasi"), ("medical", "Tibbiy ma'lumotnoma"), ("pickup", "Olib ketish ruxsati"), ("other", "Boshqa")], max_length=12)),
        ("title", models.CharField(max_length=160)),
        ("file", models.FileField(upload_to=apps.school.models.child_document_path)),
        ("valid_until", models.DateField(blank=True, null=True)),
        ("is_archived", models.BooleanField(default=False)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("child", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="documents", to="school.child")),
        ("kindergarten", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="child_documents", to="school.kindergarten")),
        ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="accounts.user")),
    ], options={"ordering": ["-created_at"]})]
