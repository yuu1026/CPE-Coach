from django.db import migrations,models


class Migration(migrations.Migration):
    dependencies=[('coach','0006_problem_output_comparison')]
    operations=[migrations.AlterField(model_name='submission',name='hint_level',field=models.PositiveSmallIntegerField(default=1))]
