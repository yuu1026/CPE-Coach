from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('coach', '0005_problemcompletion')]
    operations = [migrations.AddField(
        model_name='problem', name='output_comparison',
        field=models.CharField(max_length=20, default='exact', choices=[('exact', '文字比對'), ('line_rstrip', '忽略各行結尾空白'), ('float_1e-6', '數值絕對誤差 1e-6')]),
    )]
