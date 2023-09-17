# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2019-06-23 07:15
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    def feed_cashbox_balance_data(apps, schema_editor):
        Period = apps.get_model('cashbox_management', 'Period')
        Membership = apps.get_model('cashbox_management', 'Membership')
        for period in Period.objects.all():
            period_balance = 0
            for membership in Membership.objects.filter(period=period):
                period_balance += membership.balance
            period_hamyan_balance = period_balance - period.bank_balance
            period.hamyan_balance = period_hamyan_balance
            period.save()
            # set membership percentage balance    
            for membership in Membership.objects.filter(period=period):
                if membership.balance != 0:
                    membership.percentage_balance = membership.balance / period_balance
                    membership.save()


    dependencies = [
        ('cashbox_management', '0039_auto_20190612_2008'),
    ]

    operations = [
        migrations.AddField(
            model_name='membership',
            name='percentage_balance',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='period',
            name='hamyan_balance',
            field=models.IntegerField(blank=True, default=0, null=True, verbose_name='Hamyan Balance'),
        ),
        migrations.RunPython(feed_cashbox_balance_data, reverse_code=migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='membership',
            name='balance',
        ),
    ]
