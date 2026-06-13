# Agendamiento de citas para pacientes

**Rama:** `feature/agendamiento-citas-paciente`  
**Fecha:** Junio 2026  
**Dev:** Sebastian

---

## ¿Qué se hizo y por qué?

La idea era implementar el flujo completo para que un paciente pueda agendar una cita médica desde el frontend. Básicamente el frontend necesitaba cuatro pasos: elegir especialidad, elegir médico, ver el calendario con los horarios disponibles y confirmar la cita. Todo eso requería endpoints nuevos porque hasta ahora el backend solo tenía el login y el registro de pacientes.

Los modelos ya estaban — alguien los hizo bien desde el principio. Solo faltaban los serializers, las vistas y las URLs.

---

## Archivos creados y modificados

### Resumen rápido

| Archivo | Estado | Descripción |
|---|---|---|
| `specialties/serializers.py` | Nuevo | Serializer de especialidad con conteo de médicos disponibles |
| `specialties/views.py` | Modificado | Vista para listar especialidades activas con médicos |
| `specialties/urls.py` | Nuevo | URL `GET /api/specialties/` |
| `specialties/tests.py` | Modificado | 7 tests del endpoint de especialidades |
| `doctor/serializers.py` | Nuevo | Serializer con nombre completo, especialidades y próxima fecha |
| `doctor/views.py` | Modificado | Vista para listar médicos por especialidad |
| `doctor/urls.py` | Nuevo | URL `GET /api/doctors/` |
| `doctor/tests.py` | Modificado | 9 tests del endpoint de médicos |
| `availability/serializers.py` | Nuevo | Serializer de franja horaria |
| `availability/views.py` | Nuevo | Lógica de generación de slots libres |
| `availability/urls.py` | Nuevo | URL `GET /api/availability/slots/` |
| `availability/tests.py` | Nuevo | 11 tests del endpoint de disponibilidad |
| `appointment/serializers.py` | Nuevo | Serializers de creación, listado y detalle de citas |
| `appointment/views.py` | Modificado | 3 vistas: crear, listar y ver detalle de citas |
| `appointment/urls.py` | Nuevo | URLs de citas |
| `appointment/tests.py` | Modificado | 24 tests del flujo completo de agendamiento |
| `notifications/services.py` | Nuevo | Función de envío de correo de confirmación |
| `config/urls.py` | Modificado | Registro de las 4 nuevas apps |
| `config/settings/base.py` | Modificado | Configuración de email por variables de entorno |

---

## Lo que se implementó

### Especialidades — `specialties/`

El endpoint `GET /api/specialties/` devuelve solo las especialidades activas que tienen al menos un médico con disponibilidad en los próximos 30 días. Además cada especialidad trae cuántos médicos tiene disponibles. La idea es que el paciente no vea especialidades fantasma donde no hay nadie para atenderlo.

**Respuesta de ejemplo:**
```json
[
  {
    "id": 1,
    "name": "Medicina General",
    "description": "Atención médica primaria",
    "available_doctors_count": 3
  }
]
```

---

### Médicos — `doctor/`

El endpoint `GET /api/doctors/?specialty=<id>` trae los médicos de esa especialidad que tengan disponibilidad real en los próximos 30 días. Cada médico muestra su nombre completo, sus especialidades y la próxima fecha en que puede atender — descontando los días que tenga bloqueados por vacaciones, festivos o cualquier excepción registrada en el sistema.

Si un médico no tiene ningún día libre en los próximos 30 días simplemente no aparece en el listado.

**Respuesta de ejemplo:**
```json
[
  {
    "id": 1,
    "full_name": "Carlos Perez",
    "specialties": [{"id": 1, "name": "Medicina General"}],
    "next_available_date": "2026-06-17"
  }
]
```

---

### Franjas horarias — `availability/`

La app estaba completamente vacía — se crearon `serializers.py`, `views.py`, `urls.py` y `tests.py` desde cero.

El endpoint es `GET /api/availability/slots/?doctor=<id>&specialty=<id>&date=<YYYY-MM-DD>&view=week|month`.

Lo que hace por debajo: toma el horario semanal del médico (`DoctorAvailability`), lo expande día por día en el rango pedido, descarta los días que el médico tenga bloqueados (`ScheduleException`), y de los días que quedan quita las franjas que ya están ocupadas por citas confirmadas o pendientes. Lo que sobra son los slots libres.

Por defecto muestra una semana (7 días desde la fecha indicada). Si se manda `view=month` muestra 30 días. Las franjas pasadas no aparecen.

**Respuesta de ejemplo:**
```json
{
  "view": "week",
  "start_date": "2026-06-16",
  "end_date": "2026-06-22",
  "slots": [
    {
      "date": "2026-06-17",
      "start_time": "08:00:00",
      "end_time": "08:30:00",
      "duration_minutes": 30,
      "headquarters_id": 1,
      "headquarters_name": "Sede Central"
    }
  ]
}
```

---

### Citas — `appointment/`

Tres endpoints:

- `GET /api/appointments/` — historial del paciente, ordenado de más reciente a más antiguo.
- `GET /api/appointments/<id>/` — detalle de una cita.
- `POST /api/appointments/book/` — crear cita con todas las validaciones.

**Body para agendar:**
```json
{
  "doctor_id": 1,
  "specialty_id": 1,
  "scheduled_at": "2026-06-17T09:00:00",
  "consultation_reason": "Control general"
}
```

**Respuesta exitosa (201):**
```json
{
  "id": 42,
  "patient_name": "Maria Lopez",
  "doctor_name": "Dr(a). Carlos Perez",
  "specialty_name": "Medicina General",
  "headquarters_name": "Sede Central",
  "scheduled_at": "2026-06-17T09:00:00-05:00",
  "duration_minutes": 30,
  "status": "confirmada",
  "consultation_reason": "Control general",
  "notes": "",
  "created_at": "2026-06-13T..."
}
```

#### El flujo de validaciones

Cuando el paciente manda a reservar una franja, antes de crear la cita se validan estas cosas en orden. Si alguna falla se devuelve un mensaje específico:

1. **Franja válida** — que el `scheduled_at` exista como slot alineado en el `DoctorAvailability` del médico (no se puede mandar cualquier hora).
2. **Sin excepción** — que el médico no tenga bloqueado ese día (`ScheduleException`).
3. **Franja libre** — que ninguna otra cita confirmada o pendiente ocupe ese horario.
4. **Sin solapamiento del paciente** — que el mismo paciente no tenga otra cita que se traslape.
5. **Restricción de frecuencia** — que no haya excedido el límite de citas por semana/mes para esa especialidad (`FrequencyRestriction`).
6. **Tope EPS** — que su EPS no haya alcanzado el tope de citas para esa especialidad en el período (`EPSAppointmentLimit`).
7. **Presupuesto EPS** — que la EPS tenga presupuesto disponible (`EPSBudget`).

Si el paciente no tiene EPS, los puntos 6 y 7 se saltan directamente.

Si todo pasa, se crea la cita con estado `confirmada` y se dispara el correo de confirmación.

#### Concurrencia

Dos pacientes pueden intentar reservar la misma franja exactamente al mismo tiempo. Para manejarlo, al entrar a la transacción se hace un `select_for_update()` sobre la fila del médico en la BD. Esto hace que la segunda solicitud espere hasta que la primera termine. Cuando la primera ya creó la cita y suelta el lock, la segunda entra, revisa y encuentra la franja ocupada, y devuelve `"Esta franja ya no está disponible."`.

---

### Notificaciones — `notifications/`

Se creó `services.py` con la función `send_appointment_confirmation()`. Arma el correo con los datos de la cita, guarda un registro en la tabla `notificaciones` con estado `pendiente`, intenta el envío y actualiza el estado a `enviada` o `fallida` según el resultado. Si el correo falla, la cita ya fue creada y no se revierte — solo queda el registro de fallo para auditoria.

---

### Configuración

**`config/urls.py`** — se registraron las cuatro nuevas apps:
```
/api/specialties/
/api/doctors/
/api/availability/
/api/appointments/
```

**`config/settings/base.py`** — se agregó la configuración de email leyendo variables de entorno. En local por defecto usa el backend de consola (los correos salen en la terminal, no se envían de verdad). Para producción hay que setear las variables en el `.env`:

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.tuproveedor.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=correo@tudominio.com
EMAIL_HOST_PASSWORD=lacontraseña
DEFAULT_FROM_EMAIL=noreply@saludagendax.com
```

---

## Lo que NO se tocó

- Los modelos — ya estaban bien, no se modificó ninguno.
- El sistema de autenticación — sigue igual.
- El registro de pacientes — sigue igual.
- Las migraciones — no hubo cambios en modelos así que no se necesitaron.

---

## Bug encontrado y corregido durante los tests

Al escribir el test `test_rejects_slot_that_is_not_in_doctor_availability`, el sistema aceptaba horarios completamente inválidos como las 23:00 cuando el médico solo atiende de 8:00 a 17:00.

El problema estaba en la lógica de validación del slot en `appointment/views.py`. La condición original solo verificaba que la hora del slot fuera mayor a la hora de inicio del médico, pero no chequeaba que estuviera alineada con los intervalos de duración ni que cupiera dentro de la ventana de atención.

**Antes:**
```python
slot_end_time = (datetime.combine(date, avail.start_time) + timedelta(minutes=duration)).time()
if avail.start_time <= slot_time and slot_end_time <= avail.end_time:
    return avail
```

**Después:**
```python
start_min = avail.start_time.hour * 60 + avail.start_time.minute
slot_min  = slot_time.hour * 60 + slot_time.minute
end_min   = avail.end_time.hour * 60 + avail.end_time.minute

offset = slot_min - start_min
if offset < 0: continue
if offset % avail.appointment_duration != 0: continue   # alineación
if slot_min + avail.appointment_duration > end_min: continue  # cabe dentro
return avail
```

También se corrigió en el mismo archivo un bug con los filtros `__in=[objeto, None]` en las validaciones de EPS y frecuencia. En SQL, `IN (NULL)` no matchea nulos — lo correcto es usar `Q(specialty=specialty) | Q(specialty__isnull=True)`.

---

## Tests

Se escribieron **51 tests** en total, distribuidos en 4 archivos. Todos corren con SQLite en memoria (configuración `ENVIRONMENT=test`) para no tocar la base de datos real.

Para correrlos:
```bash
ENVIRONMENT=test python manage.py test specialties.tests doctor.tests availability.tests appointment.tests --verbosity=2
```

---

### `specialties/tests.py` — 7 tests

**Clase:** `SpecialtyListTests`

| Test | Qué verifica |
|---|---|
| `test_returns_active_specialties_that_have_available_doctors` | El endpoint devuelve las especialidades activas que tienen médicos con disponibilidad |
| `test_includes_available_doctors_count` | El campo `available_doctors_count` llega con el valor correcto |
| `test_count_increases_when_second_doctor_joins_specialty` | El conteo sube cuando se agrega un segundo médico con disponibilidad |
| `test_excludes_inactive_specialties` | Las especialidades con `active=False` no aparecen |
| `test_excludes_specialties_without_doctors_available_in_next_30_days` | Una especialidad sin médicos no aparece aunque esté activa |
| `test_excludes_specialties_whose_only_availability_is_inactive` | Una especialidad cuyo único médico tiene disponibilidad inactiva no aparece |
| `test_requires_authentication` | Sin JWT devuelve 401 |

---

### `doctor/tests.py` — 9 tests

**Clase:** `DoctorListTests`

| Test | Qué verifica |
|---|---|
| `test_returns_doctors_for_requested_specialty` | El endpoint devuelve el médico de la especialidad pedida |
| `test_doctor_response_includes_full_name_specialties_and_next_date` | Los tres campos clave llegan en la respuesta |
| `test_next_available_date_is_within_next_30_days` | La próxima fecha disponible está dentro del horizonte de 30 días |
| `test_doctor_specialties_list_includes_name_and_id` | La lista de especialidades del médico trae id y name |
| `test_excludes_doctors_without_availability_in_next_30_days` | Un médico sin disponibilidad configurada no aparece |
| `test_excludes_doctors_whose_available_days_are_all_blocked_by_exceptions` | Un médico con todos sus días bloqueados por excepciones no aparece |
| `test_does_not_return_doctors_from_other_specialties` | No se filtran médicos de otra especialidad |
| `test_returns_400_when_specialty_param_is_missing` | Sin el query param `specialty` devuelve 400 |
| `test_requires_authentication` | Sin JWT devuelve 401 |

---

### `availability/tests.py` — 11 tests

**Clase:** `AvailableSlotsTests`

| Test | Qué verifica |
|---|---|
| `test_returns_slots_with_expected_fields` | Cada slot trae `date`, `start_time`, `end_time`, `duration_minutes`, `headquarters_id`, `headquarters_name` |
| `test_default_view_is_weekly` | Sin parámetro `view`, devuelve 7 días |
| `test_month_view_covers_30_days` | Con `view=month` devuelve slots en un rango de 30 días |
| `test_slots_include_correct_duration_and_headquarters` | La duración y sede coinciden con la disponibilidad configurada |
| `test_excludes_days_blocked_by_schedule_exception` | Los días con excepción no tienen slots |
| `test_excludes_already_booked_slots` | Una franja con cita confirmada no aparece |
| `test_still_shows_remaining_slots_when_one_is_booked` | Al estar ocupada la franja de las 8:00, la de las 8:30 sí aparece |
| `test_returns_empty_slots_when_doctor_has_no_availability_for_specialty` | Sin disponibilidad para esa especialidad devuelve lista vacía |
| `test_returns_400_when_doctor_or_specialty_is_missing` | Sin `doctor` o sin `specialty` devuelve 400 |
| `test_returns_400_for_invalid_date_format` | Una fecha mal formateada devuelve 400 |
| `test_requires_authentication` | Sin JWT devuelve 401 |

---

### `appointment/tests.py` — 24 tests

**Clase `AppointmentCreateTests` — 13 tests**

| Test | Qué verifica |
|---|---|
| `test_creates_appointment_with_confirmed_status` | La cita se crea con estado `confirmada` y devuelve 201 |
| `test_response_includes_expected_appointment_fields` | La respuesta trae id, doctor_name, specialty_name, scheduled_at, status |
| `test_sends_confirmation_notification` | Se llama a `send_appointment_confirmation` con la cita creada |
| `test_blocks_slot_so_second_patient_cannot_book_same_time` | El segundo paciente recibe "Esta franja ya no está disponible" |
| `test_rejects_when_patient_already_has_overlapping_appointment` | El mismo paciente no puede tener dos citas en el mismo horario |
| `test_rejects_slot_that_is_not_in_doctor_availability` | Una hora fuera del horario del médico (ej. 23:00) devuelve 400 |
| `test_rejects_when_doctor_has_schedule_exception_on_that_day` | Si el médico tiene vacaciones ese día devuelve 400 |
| `test_rejects_when_frequency_restriction_is_exceeded` | Si el paciente ya llegó al límite de citas por período devuelve 400 |
| `test_rejects_when_eps_appointment_limit_is_exceeded` | Si la EPS ya alcanzó el tope de citas devuelve 400 |
| `test_rejects_when_eps_has_no_remaining_budget` | Si la EPS no tiene presupuesto devuelve 400 |
| `test_rejects_non_patient_user` | Un usuario administrativo o médico recibe 403 |
| `test_requires_authentication` | Sin JWT devuelve 401 |
| `test_returns_400_when_required_fields_are_missing` | Sin `doctor_id` ni `specialty_id` devuelve 400 con los campos en error |
| `test_does_not_apply_eps_validations_when_patient_has_no_eps` | Si el paciente no tiene EPS, las validaciones de tope y presupuesto se saltan |

**Clase `AppointmentListTests` — 6 tests**

| Test | Qué verifica |
|---|---|
| `test_returns_appointments_for_authenticated_patient` | El paciente ve sus citas |
| `test_response_includes_expected_fields` | Cada cita trae id, doctor_name, specialty_name, scheduled_at, status |
| `test_does_not_return_other_patients_appointments` | El paciente solo ve sus propias citas, no las de otros |
| `test_returns_empty_list_when_patient_has_no_appointments` | Sin citas devuelve lista vacía con 200 |
| `test_requires_authentication` | Sin JWT devuelve 401 |
| `test_rejects_non_patient_user` | Un usuario no paciente recibe 403 |

**Clase `AppointmentDetailTests` — 4 tests**

| Test | Qué verifica |
|---|---|
| `test_returns_full_appointment_detail` | El detalle trae todos los campos: id, doctor, especialidad, sede, estado |
| `test_rejects_access_to_another_patients_appointment` | Un paciente no puede ver la cita de otro paciente |
| `test_returns_400_for_nonexistent_appointment` | Un id que no existe devuelve 400 |
| `test_requires_authentication` | Sin JWT devuelve 401 |

---

## Cómo probar rápido (manual)

Todos los endpoints requieren el header `Authorization: Bearer <token>` con un JWT válido de un paciente.

```
# 1. Ver especialidades disponibles
GET /api/specialties/

# 2. Ver médicos de una especialidad
GET /api/doctors/?specialty=1

# 3. Ver horarios disponibles (vista semanal)
GET /api/availability/slots/?doctor=1&specialty=1&date=2026-06-16

# 4. Ver horarios en vista mensual
GET /api/availability/slots/?doctor=1&specialty=1&date=2026-06-16&view=month

# 5. Agendar una cita
POST /api/appointments/book/
{
  "doctor_id": 1,
  "specialty_id": 1,
  "scheduled_at": "2026-06-17T09:00:00",
  "consultation_reason": "Control general"
}

# 6. Ver mis citas
GET /api/appointments/

# 7. Ver detalle de una cita
GET /api/appointments/42/
```
