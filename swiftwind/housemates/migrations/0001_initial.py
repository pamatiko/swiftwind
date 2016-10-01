# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-09-27 23:00
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_smalluuid.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('hordak', '0003_check_zero_amount_20160907_0921'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Housemate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', django_smalluuid.models.SmallUUIDField(default=django_smalluuid.models.UUIDDefault(), editable=False, unique=True)),
                ('account', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='housemate', to='hordak.Account')),
                ('user', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='houesmate', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]