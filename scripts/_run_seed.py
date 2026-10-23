import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
import django
django.setup()
from scripts.seed import run
run()
from scripts._check import *
