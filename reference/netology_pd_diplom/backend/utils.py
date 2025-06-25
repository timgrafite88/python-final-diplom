import os
from django.core.exceptions import ValidationError
from yaml import load as load_yaml, Loader
import csv
import json
from datetime import datetime
from backend.models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter


def import_file(file_path, user):
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext in ('.yaml', '.yml'):
        return import_yaml(file_path, user)
    elif ext == '.csv':
        return import_csv(file_path, user)
    elif ext == '.json':
        return import_json(file_path, user)
    else:
        raise ValidationError("Неподдерживаемый формат файла")


def import_yaml(file_path, user):
    stats = {'created': 0, 'updated': 0, 'errors': 0}
    with open(file_path, 'r', encoding='utf-8') as file:
        data = load_yaml(file, Loader=Loader)
        shop_name = data['shop']
        shop, _ = Shop.objects.get_or_create(name=shop_name, user=user)

        for category_data in data.get('categories', []):
            category, _ = Category.objects.get_or_create(
                id=category_data['id'],
                defaults={'name': category_data['name']}
            )
            category.shops.add(shop)
            category.save()

        for product_data in data.get('goods', []):
            try:
                product, _ = Product.objects.get_or_create(
                    name=product_data['name'],
                    category_id=product_data['category']
                )

                product_info, created = ProductInfo.objects.update_or_create(
                    product=product,
                    shop=shop,
                    external_id=product_data['id'],
                    defaults={
                        'model': product_data.get('model', ''),
                        'price': product_data['price'],
                        'price_rrc': product_data.get('price_rrc', product_data['price']),
                        'quantity': product_data['quantity'],
                        'discount': product_data.get('discount', 0)
                    }
                )

                if created:
                    stats['created'] += 1
                else:
                    stats['updated'] += 1

                for name, value in product_data.get('parameters', {}).items():
                    parameter, _ = Parameter.objects.get_or_create(name=name)
                    ProductParameter.objects.update_or_create(
                        product_info=product_info,
                        parameter=parameter,
                        defaults={'value': value}
                    )

            except Exception as e:
                stats['errors'] += 1
                continue

    return stats


def import_csv(file_path, user):
    # Реализация импорта из CSV
    pass


def import_json(file_path, user):
    # Реализация импорта из JSON
    pass