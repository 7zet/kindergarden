import re
import uuid

import django.db.models.deletion
from django.db import migrations, models


def normalize(value):
    digits = re.sub(r"\D", "", value or "")
    return "998" + digits if len(digits) == 9 else digits


def move_identities(apps, schema_editor):
    Contact = apps.get_model("school", "Contact")
    Person = apps.get_model("school", "Person")
    ContactPass = apps.get_model("school", "ContactPass")
    TelegramAccount = apps.get_model("school", "TelegramAccount")
    cache = {}
    for contact in Contact.objects.select_related("child").order_by("created_at"):
        key = (contact.child.kindergarten_id, normalize(contact.phone),
               (contact.full_name or "").strip().casefold())
        # Telefon bo'sh bo'lsa hech qachon avtomatik birlashtirmaymiz.
        if not key[1]:
            key = (*key, contact.id)
        person = cache.get(key)
        if person is None:
            person = Person.objects.create(
                kindergarten_id=contact.child.kindergarten_id,
                full_name=contact.full_name, phone=contact.phone,
                normalized_phone=normalize(contact.phone),
            )
            cache[key] = person
        contact.person_id = person.id
        contact.save(update_fields=["person"])

    for account in TelegramAccount.objects.all():
        person_ids = Contact.objects.filter(
            telegram_accounts=account).values_list("person_id", flat=True).distinct()
        account.persons.add(*person_ids)
    for item in ContactPass.objects.select_related("contact"):
        item.person_id = item.contact.person_id
        item.save(update_fields=["person"])


class Migration(migrations.Migration):
    dependencies = [("school", "0018_kindergarten_bank_account_kindergarten_bank_mfo_and_more")]
    operations = [
        migrations.CreateModel(
            name="Person",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("full_name", models.CharField(max_length=160, verbose_name="F.I.O.")),
                ("phone", models.CharField(blank=True, max_length=20, verbose_name="Telefon")),
                ("normalized_phone", models.CharField(blank=True, db_index=True, editable=False, max_length=20)),
                ("note", models.CharField(blank=True, max_length=200, verbose_name="Shaxs haqida izoh")),
                ("is_active", models.BooleanField(default=True, verbose_name="Faol")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("kindergarten", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                    related_name="persons", to="school.kindergarten")),
            ],
            options={"ordering": ["full_name"]},
        ),
        migrations.AddIndex(model_name="person", index=models.Index(
            fields=["kindergarten", "normalized_phone"], name="school_pers_kinderg_9c8618_idx")),
        migrations.AddField(model_name="contact", name="person", field=models.ForeignKey(
            null=True, on_delete=django.db.models.deletion.CASCADE,
            related_name="contacts", to="school.person")),
        migrations.AddField(model_name="telegramaccount", name="persons",
                            field=models.ManyToManyField(blank=True,
                                related_name="telegram_accounts", to="school.person")),
        migrations.AddField(model_name="contactpass", name="person", field=models.ForeignKey(
            null=True, on_delete=django.db.models.deletion.CASCADE,
            related_name="contact_passes", to="school.person")),
        migrations.RunPython(move_identities, migrations.RunPython.noop),
        migrations.AlterField(model_name="contact", name="person", field=models.ForeignKey(
            on_delete=django.db.models.deletion.CASCADE, related_name="contacts", to="school.person")),
        migrations.AlterField(model_name="contactpass", name="person", field=models.ForeignKey(
            on_delete=django.db.models.deletion.CASCADE, related_name="contact_passes", to="school.person")),
        migrations.RemoveField(model_name="telegramaccount", name="contacts"),
        migrations.RemoveField(model_name="contactpass", name="contact"),
        migrations.RemoveField(model_name="contact", name="full_name"),
        migrations.RemoveField(model_name="contact", name="phone"),
        migrations.AlterModelOptions(name="contact", options={
            "ordering": ["-is_primary", "kind", "person__full_name"]}),
        migrations.AddConstraint(model_name="contact", constraint=models.UniqueConstraint(
            fields=("person", "child"), name="unique_person_child_contact")),
        migrations.CreateModel(name="ContactChild", fields=[], options={
            "verbose_name": "Bola kontakti", "verbose_name_plural": "Bola kontaktlari",
            "proxy": True, "indexes": [], "constraints": []}, bases=("school.contact",)),
    ]
