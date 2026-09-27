from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0010_move_contacts"),
    ]

    operations = [
        migrations.RemoveField(model_name="child", name="parent_name"),
        migrations.RemoveField(model_name="child", name="parent_phone"),
        migrations.RemoveField(model_name="child", name="parent_phone_2"),
        migrations.RemoveField(model_name="child", name="emergency_name"),
        migrations.RemoveField(model_name="child", name="emergency_phone"),
    ]
