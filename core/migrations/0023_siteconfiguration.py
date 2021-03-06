# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2018-07-30 15:45
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_appcustomization_email_language_toggle'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activate_site_configuration', models.BooleanField(default=False)),
                ('elgg_url', models.CharField(blank=True, max_length=255, null=True)),
                ('freshdesk_url', models.CharField(blank=True, max_length=255, null=True)),
                ('freshdesk_secret_key', models.CharField(blank=True, max_length=255, null=True)),
                ('from_email', models.CharField(blank=True, max_length=255, null=True)),
                ('email_host', models.CharField(blank=True, max_length=255, null=True)),
                ('email_port', models.IntegerField(blank=True, null=True)),
                ('email_user', models.CharField(blank=True, max_length=255, null=True)),
                ('email_password', models.CharField(blank=True, max_length=255, null=True)),
                ('email_use_tls', models.BooleanField(default=True)),
                ('cors_origin_whitelist', models.CharField(blank=True, max_length=255, null=True)),
                ('profile_as_service_endpoint', models.CharField(blank=True, max_length=255, null=True)),
                ('password_reset_timeout_days', models.IntegerField(default='1')),
                ('account_activation_days', models.IntegerField(default='7')),
                ('send_suspicious_behaviour_warnings', models.BooleanField(default=False)),
            ],
            options={
                'verbose_name': 'Site Configuration',
            },
        ),
    ]
