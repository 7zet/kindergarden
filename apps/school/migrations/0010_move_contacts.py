from django.db import migrations


def move_contacts(apps, schema_editor):
    Child = apps.get_model("school", "Child")
    Contact = apps.get_model("school", "Contact")
    for child in Child.objects.all():
        if child.parent_phone:
            Contact.objects.create(
                child=child,
                full_name=child.parent_name or "Ota-ona",
                relation="Ota-ona",
                phone=child.parent_phone,
                kind="parent",
                is_primary=True,
                is_payer=True,
                can_pickup=True,
                has_app_access=True,
                can_see_billing=True,
                receives_messages=True,
            )
        if child.parent_phone_2:
            Contact.objects.create(
                child=child,
                full_name="Qo'shimcha aloqa",
                relation="Qarindosh",
                phone=child.parent_phone_2,
                kind="family",
                can_pickup=True,
            )
        if child.emergency_phone:
            Contact.objects.create(
                child=child,
                full_name=child.emergency_name or "Favqulodda",
                relation="Favqulodda",
                phone=child.emergency_phone,
                kind="emergency",
            )


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0009_contact"),
    ]

    operations = [
        migrations.RunPython(move_contacts, migrations.RunPython.noop),
    ]
