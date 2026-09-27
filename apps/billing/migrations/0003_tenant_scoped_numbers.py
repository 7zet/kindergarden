from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("billing", "0002_alter_payment_amount_alter_payment_child_and_more")]
    operations = [
        migrations.RemoveConstraint(model_name="payment", name="uniq_provider_txn"),
        migrations.AlterField(model_name="invoice", name="number",
                              field=models.CharField(max_length=48)),
        migrations.AddConstraint(model_name="invoice", constraint=models.UniqueConstraint(
            fields=("kindergarten", "number"), name="uniq_invoice_number_per_tenant")),
        migrations.AddConstraint(model_name="payment", constraint=models.UniqueConstraint(
            condition=models.Q(external_id__gt=""),
            fields=("kindergarten", "method", "external_id"),
            name="uniq_provider_txn_per_tenant")),
    ]
