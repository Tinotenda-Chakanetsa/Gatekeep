from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from gate.models import GateDevice, Person, Vehicle

User = get_user_model()


class Command(BaseCommand):
    help = 'Create initial admin/operator accounts, a gate device, and sample vehicles.'

    def handle(self, *args, **options):
        admin_user, created = User.objects.get_or_create(
            username=os.environ.get('SEED_ADMIN_USER', 'admin'),
            defaults={'role': User.Role.ADMIN, 'is_staff': True, 'is_superuser': True},
        )
        if created:
            admin_user.set_password(os.environ.get('SEED_ADMIN_PASSWORD', 'admin12345'))
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(f'Created admin "{admin_user.username}" (password: admin12345)'))
        else:
            self.stdout.write(f'Admin "{admin_user.username}" already exists.')

        operator, created = User.objects.get_or_create(
            username='operator',
            defaults={'role': User.Role.OPERATOR, 'is_staff': False},
        )
        if created:
            operator.set_password('operator12345')
            operator.save()
            self.stdout.write(self.style.SUCCESS('Created operator "operator" (password: operator12345)'))

        device, created = GateDevice.objects.get_or_create(
            name='Main Gate Camera',
            defaults={'location': 'Front entrance'},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created device "{device.name}" with key: {device.api_key}'))
        else:
            self.stdout.write(f'Device key for "{device.name}": {device.api_key}')

        sample = [
            ('Alice Mwangi', 'A-12', [('KDA 123A', 'Toyota', 'Axio', 'Silver')]),
            ('John Otieno', 'B-04', [('KBZ 456B', 'Mazda', 'Demio', 'Blue'), ('KCX 789C', 'Nissan', 'Note', 'White')]),
        ]
        for full_name, unit, vehicles in sample:
            person, _ = Person.objects.get_or_create(full_name=full_name, defaults={'unit': unit})
            for plate, make, model, color in vehicles:
                Vehicle.objects.get_or_create(
                    display_plate=plate,
                    defaults={'owner': person, 'make': make, 'model': model, 'color': color},
                )
        self.stdout.write(self.style.SUCCESS('Sample people and vehicles ensured.'))
