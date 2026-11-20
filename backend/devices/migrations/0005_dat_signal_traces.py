import uuid

import django.contrib.postgres.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('devices', '0004_testrun_flat_result_data')]

    operations = [
        migrations.AddField(
            model_name='testrun', name='source_file_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='testrun', name='source_file_sha256',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='testrun', name='source_device_index',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='testrun', name='source_test_index',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='testrun', name='source_operator_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddConstraint(
            model_name='testrun',
            constraint=models.UniqueConstraint(
                fields=('source_file_sha256', 'source_device_index', 'source_test_index'),
                name='test_runs_source_position_unique',
            ),
        ),
        migrations.CreateModel(
            name='SignalTrace',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('samples', django.contrib.postgres.fields.ArrayField(base_field=models.FloatField(), size=None)),
                ('signal_definition', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='traces', to='devices.signaldefinition',
                )),
                ('test_run', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='signal_traces', to='devices.testrun',
                )),
            ],
            options={
                'db_table': 'signal_traces',
                'ordering': ['signal_definition__name', 'id'],
                'constraints': [models.UniqueConstraint(
                    fields=('test_run', 'signal_definition'),
                    name='signal_traces_run_definition_unique',
                )],
            },
        ),
    ]
