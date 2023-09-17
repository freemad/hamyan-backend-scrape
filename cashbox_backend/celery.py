from __future__ import absolute_import, unicode_literals

import os

from celery import Celery
from django.conf import settings
from kombu import Queue

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cashbox_backend.settings")

app = Celery(
    "cashbox_backend",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Using a string here means the worker don't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.timezone = "Asia/Tehran"


app.conf.task_queues = (
    Queue('default'),
    Queue('high_priority'),
)


# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
