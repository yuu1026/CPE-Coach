from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('coach', '0007_default_legacy_hint_level')]
    operations = [migrations.AddField(model_name='submission', name='performance', field=models.JSONField(default=dict, blank=True))]
