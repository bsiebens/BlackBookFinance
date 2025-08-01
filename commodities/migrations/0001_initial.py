# Generated by Django 5.2.4 on 2025-07-29 08:10

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Commodity",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, verbose_name="name")),
                ("code", models.CharField(max_length=10, verbose_name="name")),
            ],
            options={
                "verbose_name": "commodity",
                "verbose_name_plural": "commodities",
                "ordering": ["name", "code"],
            },
        ),
    ]
