# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2018-07-28 09:37
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('moneypool_management', '0003_auto_20180727_2033'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='moneypool',
            name='hamyan_balance',
        ),
    ]
