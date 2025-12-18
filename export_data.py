"""
Custom data export script for FILL11
Handles PhoneNumber fields properly
Save this as: export_data.py in your project root
"""

import json
from django.core.management.base import BaseCommand
from django.apps import apps
from django.core.serializers.json import DjangoJSONEncoder
from phonenumber_field.phonenumber import PhoneNumber


class PhoneNumberEncoder(DjangoJSONEncoder):
    """Custom JSON encoder that handles PhoneNumber objects and Files"""
    def default(self, obj):
        if isinstance(obj, PhoneNumber):
            return str(obj)  # Convert PhoneNumber to string
        from django.db.models.fields.files import FieldFile
        if isinstance(obj, FieldFile):
            return obj.name if obj else None  # Convert File to file path
        return super().default(obj)


def export_all_data():
    """Export all data from all models"""
    data = []

    # Get all models
    for model in apps.get_models():
        # Skip contenttypes, permissions, and admin logs
        if model._meta.app_label == 'contenttypes':
            continue
        if model._meta.app_label == 'admin':  # Skip admin logs
            continue
        if model._meta.model_name == 'permission':
            continue
        if model._meta.model_name == 'session':  # Skip sessions
            continue

        print(f"Exporting {model._meta.app_label}.{model._meta.model_name}...")

        for obj in model.objects.all():
            model_data = {
                'model': f"{model._meta.app_label}.{model._meta.model_name}",
                'pk': obj.pk,
                'fields': {}
            }

            # Get all fields
            for field in model._meta.fields:
                if field.name == 'id':
                    continue

                field_value = getattr(obj, field.name)

                # Handle PhoneNumber fields
                if isinstance(field_value, PhoneNumber):
                    model_data['fields'][field.name] = str(field_value)
                # Handle File/Image fields
                elif hasattr(field_value, 'name'):  # FileField or ImageField
                    model_data['fields'][field.name] = field_value.name if field_value else None
                # Handle foreign keys
                elif hasattr(field, 'related_model') and field.related_model:
                    if field_value:
                        model_data['fields'][field.name] = field_value.pk
                    else:
                        model_data['fields'][field.name] = None
                # Handle other fields
                else:
                    model_data['fields'][field.name] = field_value

            data.append(model_data)

    return data


if __name__ == '__main__':
    import os
    import django

    # Setup Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fill11.settings')
    django.setup()

    print("Starting data export...")
    data = export_all_data()

    # Write to file
    with open('datadump.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, cls=PhoneNumberEncoder, indent=2, ensure_ascii=False)

    print(f"\n✅ Successfully exported {len(data)} records to datadump.json")