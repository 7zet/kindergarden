from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_alter_user_role")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="must_change_password",
            field=models.BooleanField(
                default=False,
                help_text="Keyingi kirishda foydalanuvchi yangi parol o'rnatadi.",
                verbose_name="Parolni almashtirishi shart",
            ),
        ),
    ]
