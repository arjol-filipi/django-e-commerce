# Generated by Django 2.2.8 on 2020-01-08 21:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_order_coupon'),
    ]

    operations = [
        migrations.AddField(
            model_name='coupon',
            name='amount',
            field=models.FloatField(default=0),
            preserve_default=False,
        ),
    ]
