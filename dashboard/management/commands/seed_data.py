"""
Management command: seed_data
Uso: python manage.py seed_data

Crea datos de prueba realistas para SaludAgendaX:
- 2 EPS
- 2 Sedes
- 4 Especialidades
- 4 Médicos (con sus usuarios)
- 6 Pacientes (con sus usuarios)
- ~40 Citas distribuidas en distintos estados y fechas
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta, date, time, datetime
import random


class Command(BaseCommand):
    help = 'Pobla la base de datos con datos de prueba para el dashboard'

    def handle(self, *args, **options):
        self.stdout.write('🌱 Iniciando seed de datos...')
        try:
            with transaction.atomic():
                self._create_all()
            self.stdout.write(self.style.SUCCESS('✅ Seed completado exitosamente'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {e}'))
            raise

    def _create_all(self):
        from eps.models import EPS
        from headquarters.models import Headquarters
        from specialties.models import Specialty
        from user.models import User
        from doctor.models import Doctor, DoctorSpecialty
        from patient.models import Patient
        from appointment.models import Appointment

        # ── 1. EPS ────────────────────────────────────────────────
        eps_sura, _ = EPS.objects.get_or_create(
            code="SURA",
            defaults={
                "name": EPS.Name.SURA,
                "active": True,
            },
        )

        eps_compensar, _ = EPS.objects.get_or_create(
            code="COMPENSAR",
            defaults={
                "name": EPS.Name.COMPENSAR,
                "active": True,
            },
        )

        eps_list = [eps_sura, eps_compensar]
        # ── 2. Sedes ──────────────────────────────────────────────
        self.stdout.write('  Creando sedes...')
        sede_norte, _ = Headquarters.objects.get_or_create(
            name='Sede Norte',
            defaults={'address': 'Calle 15 # 8-21, Cali', 'active': True}
        )
        sede_sur, _ = Headquarters.objects.get_or_create(
            name='Sede Sur',
            defaults={'address': 'Carrera 5 # 30-10, Cali', 'active': True}
        )
        sedes = [sede_norte, sede_sur]

        # ── 3. Especialidades ─────────────────────────────────────
        self.stdout.write('  Creando especialidades...')
        spec_names = ['Cardiología', 'Pediatría', 'Medicina General', 'Dermatología']
        specs = []
        for name in spec_names:
            sp, _ = Specialty.objects.get_or_create(name=name)
            specs.append(sp)
        card, pedi, med_gen, derm = specs

        # ── 4. Médicos ────────────────────────────────────────────
        self.stdout.write('  Creando médicos...')
        doctors_data = [
            {
                'email': 'dr.garcia@saludagendax.com',
                'nombre': 'Andrés', 'apellido': 'García',
                'identity_document': 'MED001', 'register_number': 'RM-10001',
                'specialties': [card, med_gen],
            },
            {
                'email': 'dra.martinez@saludagendax.com',
                'nombre': 'Sofía', 'apellido': 'Martínez',
                'identity_document': 'MED002', 'register_number': 'RM-10002',
                'specialties': [pedi],
            },
            {
                'email': 'dr.rodriguez@saludagendax.com',
                'nombre': 'Carlos', 'apellido': 'Rodríguez',
                'identity_document': 'MED003', 'register_number': 'RM-10003',
                'specialties': [derm, med_gen],
            },
            {
                'email': 'dra.lopez@saludagendax.com',
                'nombre': 'Valentina', 'apellido': 'López',
                'identity_document': 'MED004', 'register_number': 'RM-10004',
                'specialties': [card, pedi],
            },
        ]

        doctors = []
        for d in doctors_data:
            user, created = User.objects.get_or_create(
                email=d['email'],
                defaults={
                    'nombre': d['nombre'],
                    'apellido': d['apellido'],
                    'rol': User.Role.DOCTOR,
                    'is_active': True,
                }
            )
            if created:
                user.set_password('Doctor2024!')
                user.save()

            doctor, _ = Doctor.objects.get_or_create(
                user=user,
                defaults={
                    'identity_document': d['identity_document'],
                    'register_number': d['register_number'],
                    'active': True,
                }
            )
            for sp in d['specialties']:
                DoctorSpecialty.objects.get_or_create(doctor=doctor, specialty=sp)

            doctors.append({'doctor': doctor, 'specialties': d['specialties']})

        # ── 5. Pacientes ──────────────────────────────────────────
        self.stdout.write('  Creando pacientes...')
        patients_data = [
            {
                'email': 'juan.perez@gmail.com', 'nombre': 'Juan', 'apellido': 'Pérez',
                'identity_document': '10001111', 'document_type': 'CC',
                'date_birth': date(1985, 3, 12), 'phone_number': '3001111111',
                'address': 'Calle 10 # 5-20', 'eps': eps_sura, 'sede': sede_norte,
            },
            {
                'email': 'maria.gomez@gmail.com', 'nombre': 'María', 'apellido': 'Gómez',
                'identity_document': '10002222', 'document_type': 'CC',
                'date_birth': date(1992, 7, 8), 'phone_number': '3002222222',
                'address': 'Carrera 8 # 12-45', 'eps': eps_sura, 'sede': sede_sur,
            },
            {
                'email': 'luis.torres@gmail.com', 'nombre': 'Luis', 'apellido': 'Torres',
                'identity_document': '10003333', 'document_type': 'CC',
                'date_birth': date(1978, 11, 25), 'phone_number': '3003333333',
                'address': 'Av. 6N # 23-10', 'eps': eps_sura, 'sede': sede_norte,
            },
            {
                'email': 'ana.ramirez@gmail.com', 'nombre': 'Ana', 'apellido': 'Ramírez',
                'identity_document': '10004444', 'document_type': 'CC',
                'date_birth': date(2001, 5, 17), 'phone_number': '3004444444',
                'address': 'Calle 5 # 8-90', 'eps': eps_sura, 'sede': sede_sur,
            },
            {
                'email': 'pedro.castillo@gmail.com', 'nombre': 'Pedro', 'apellido': 'Castillo',
                'identity_document': '10005555', 'document_type': 'CC',
                'date_birth': date(1965, 9, 3), 'phone_number': '3005555555',
                'address': 'Calle 70 # 15-30', 'eps': eps_sura, 'sede': sede_norte,
            },
            {
                'email': 'laura.vargas@gmail.com', 'nombre': 'Laura', 'apellido': 'Vargas',
                'identity_document': '10006666', 'document_type': 'CC',
                'date_birth': date(1990, 2, 28), 'phone_number': '3006666666',
                'address': 'Carrera 100 # 5-15', 'eps': eps_sura, 'sede': sede_sur,
            },
        ]

        patients = []
        for p in patients_data:
            user, created = User.objects.get_or_create(
                email=p['email'],
                defaults={
                    'nombre': p['nombre'],
                    'apellido': p['apellido'],
                    'rol': User.Role.PATIENT,
                    'is_active': True,
                }
            )
            if created:
                user.set_password('Paciente2024!')
                user.save()

            patient, _ = Patient.objects.get_or_create(
                user=user,
                defaults={
                    'identity_document': p['identity_document'],
                    'document_type': p['document_type'],
                    'date_birth': p['date_birth'],
                    'phone_number': p['phone_number'],
                    'address': p['address'],
                    'eps': p['eps'],
                    'sede': p['sede'],
                }
            )
            patients.append(patient)

        # ── 6. Usuario admin para created_by ─────────────────────
        admin_user, created = User.objects.get_or_create(
            email='admin@saludagendax.com',
            defaults={
                'nombre': 'Admin',
                'apellido': 'Sistema',
                'rol': User.Role.ADMINISTRATIVE,
                'is_active': True,
                'is_staff': True,
            }
        )
        if created:
            admin_user.set_password('Admin2024!')
            admin_user.save()

        # ── 7. Citas ──────────────────────────────────────────────
        self.stdout.write('  Creando citas...')

        today = timezone.localdate()
        statuses = [
            'confirmada', 'confirmada', 'confirmada',
            'atendida', 'atendida', 'atendida', 'atendida',
            'cancelada', 'cancelada',
            'pendiente',
            'reprogramada',
        ]
        hours = [8, 9, 10, 11, 14, 15, 16, 17]

        appointments_created = 0

        # Citas en los últimos 60 días + próximos 15 días
        for days_offset in range(-60, 15):
            appt_date = today + timedelta(days=days_offset)

            # 2-4 citas por día
            num_appts = random.randint(2, 4)

            used_slots = set()  # evitar colisiones doctor+hora

            for _ in range(num_appts):
                doctor_info = random.choice(doctors)
                doctor = doctor_info['doctor']
                specialty = random.choice(doctor_info['specialties'])
                patient = random.choice(patients)
                hour = random.choice(hours)

                # Evitar doble reserva mismo médico misma hora mismo día
                slot_key = (doctor.id, hour)
                if slot_key in used_slots:
                    continue
                used_slots.add(slot_key)

                scheduled_dt = timezone.make_aware(
                    datetime.combine(appt_date, time(hour, 0))
                )

                # Citas futuras solo pueden ser confirmadas o pendientes
                if days_offset > 0:
                    status = random.choice(['confirmada', 'pendiente'])
                else:
                    status = random.choice(statuses)

                # Citas de hoy: mezcla de todos los estados
                if days_offset == 0:
                    status = random.choice(['confirmada', 'atendida', 'cancelada', 'pendiente'])

                Appointment.objects.get_or_create(
                    doctor=doctor,
                    scheduled_at=scheduled_dt,
                    defaults={
                        'patient': patient,
                        'specialty': specialty,
                        'headquarters': random.choice(sedes),
                        'duration_minutes': 30,
                        'status': status,
                        'created_by': admin_user,
                        'consultation_reason': random.choice([
                            'Control rutinario',
                            'Consulta de seguimiento',
                            'Primera consulta',
                            'Revisión de resultados',
                            'Dolor persistente',
                        ]),
                    }
                )
                appointments_created += 1

        self.stdout.write(f'  Citas creadas/verificadas: {appointments_created}')
        self.stdout.write(f'  Médicos: {len(doctors)} | Pacientes: {len(patients)}')
        self.stdout.write(f'  EPS: 2 | Sedes: 2 | Especialidades: {len(specs)}')
