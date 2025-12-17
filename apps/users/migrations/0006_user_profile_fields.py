from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_auto_20251210_2331'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='age',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='pin_code',
            field=models.CharField(blank=True, default='', max_length=10),
        ),
        migrations.AddField(
            model_name='user',
            name='skill_role',
            field=models.CharField(choices=[('BATSMAN', 'Batsman'), ('BOWLER', 'Bowler'), ('WICKET_KEEPER', 'Wicket Keeper'), ('ALL_ROUNDER', 'All Rounder'), ('ANY', 'Any Role')], default='ANY', max_length=20),
        ),
        migrations.AlterField(
            model_name='user',
            name='name',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
    ]

