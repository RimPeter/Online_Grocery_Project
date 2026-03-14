from django.db import migrations


def seed_basket_reward_pillar(apps, schema_editor):
    HomeValuePillar = apps.get_model('_catalog', 'HomeValuePillar')

    HomeValuePillar.objects.update_or_create(
        key='basket_reward',
        defaults={
            'title': 'Unlock basket rewards',
            'subtitle': 'Reach the basket reward threshold and enjoy extra savings on bigger shops.',
            'sort_order': 30,
        },
    )

    HomeValuePillar.objects.filter(key='reorders').update(sort_order=40)


def unseed_basket_reward_pillar(apps, schema_editor):
    HomeValuePillar = apps.get_model('_catalog', 'HomeValuePillar')
    HomeValuePillar.objects.filter(key='basket_reward').delete()
    HomeValuePillar.objects.filter(key='reorders').update(sort_order=30)


class Migration(migrations.Migration):

    dependencies = [
        ('_catalog', '0014_alter_categorynodesetting_id'),
    ]

    operations = [
        migrations.RunPython(seed_basket_reward_pillar, unseed_basket_reward_pillar),
    ]
