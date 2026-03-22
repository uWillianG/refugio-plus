from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from booking.models import court_block_exceptions, court_blocks, courts, holidays, schedules, sports


class BookingRules:
    WEEKDAY_OPEN_HOUR = 15
    WEEKEND_OPEN_HOUR = 8
    CLOSE_HOUR = 23
    MAX_DURATION_HOURS = 3
    WEEKDAY_PRICE = 80
    WEEKEND_OR_HOLIDAY_PRICE = 95
    HOLIDAYS = set()

    @classmethod
    def open_hour_for_date(cls, selected_date):
        if cls.is_holiday(selected_date) or selected_date.weekday() >= 5:
            return cls.WEEKEND_OPEN_HOUR
        return cls.WEEKDAY_OPEN_HOUR

    @classmethod
    def iter_start_hours(cls, selected_date):
        open_hour = cls.open_hour_for_date(selected_date)
        return range(open_hour, cls.CLOSE_HOUR)

    @classmethod
    def is_holiday(cls, selected_date):
        if selected_date in cls.HOLIDAYS:
            return True
        return holidays.objects.filter(dates=selected_date).exists()

    @classmethod
    def price_for_date(cls, selected_date):
        if cls.is_holiday(selected_date) or selected_date.weekday() >= 5:
            return cls.WEEKEND_OR_HOLIDAY_PRICE
        return cls.WEEKDAY_PRICE


def parse_selected_date(raw_date):
    if not raw_date:
        return timezone.localdate()
    try:
        return date.fromisoformat(raw_date)
    except ValueError:
        return timezone.localdate()


def format_hour(hour_value):
    return f"{hour_value:02d}:00"


def format_price_brl(price_value):
    return f"R$ {price_value},00"


def calculate_duration_hours(start_hour, end_hour):
    duration = end_hour - start_hour
    if duration < 1:
        return 1
    return duration


def booking_total_price(selected_date, start_hour, end_hour):
    base_price = BookingRules.price_for_date(selected_date)
    duration_hours = calculate_duration_hours(start_hour, end_hour)
    return base_price * duration_hours


def booking_cancellation_deadline(booking):
    start_at = datetime.combine(booking.date, booking.start_hour)
    return timezone.make_aware(start_at, timezone.get_current_timezone()) - timedelta(hours=1)


def user_can_cancel_booking(user, booking, now=None):
    if getattr(user, "is_admin", False):
        return True

    if now is None:
        now = timezone.localtime()

    return now <= booking_cancellation_deadline(booking)


def resolve_block_model():
    return court_blocks


def python_weekday_to_django(weekday_value):
    return ((weekday_value + 1) % 7) + 1


def weekday_label(weekday_value):
    labels = [
        "segunda-feira",
        "terca-feira",
        "quarta-feira",
        "quinta-feira",
        "sexta-feira",
        "sabado",
        "domingo",
    ]
    return labels[weekday_value]


def active_block_queryset_for_date(selected_date):
    return court_blocks.objects.filter(
        is_active=True,
    ).filter(
        Q(start_at__date=selected_date)
        | Q(is_fixed=True, fixed_weekday=selected_date.weekday(), start_at__date__lte=selected_date)
    ).exclude(
        exceptions__skip_date=selected_date
    )


def load_blocked_intervals(court_id, selected_date):
    intervals = []

    schedule_rows = schedules.objects.filter(
        court_id=court_id,
        date=selected_date,
        is_active=True,
    ).values("start_hour", "end_hour")

    for row in schedule_rows:
        start_hour = row["start_hour"].hour
        end_hour = row["end_hour"].hour
        intervals.append((start_hour, end_hour))

    block_model = resolve_block_model()
    if block_model:
        block_rows = active_block_queryset_for_date(selected_date).filter(
            court_id=court_id,
        ).values("start_at", "end_at")

        for row in block_rows:
            start_at = timezone.localtime(row["start_at"])
            end_at = timezone.localtime(row["end_at"])
            start_hour = start_at.hour + (start_at.minute / 60)
            end_hour = end_at.hour + (end_at.minute / 60)
            intervals.append((start_hour, end_hour))

    return intervals


def overlaps(start_hour, end_hour, blocked_intervals):
    for blocked_start, blocked_end in blocked_intervals:
        if start_hour < blocked_end and end_hour > blocked_start:
            return True
    return False


def build_slot_matrix(selected_date, blocked_intervals):
    now = timezone.localtime()
    is_today = selected_date == now.date()
    slot_rows = []

    for start_hour in BookingRules.iter_start_hours(selected_date):
        options = []
        has_available_option = False

        for duration in range(1, BookingRules.MAX_DURATION_HOURS + 1):
            end_hour = start_hour + duration
            status = "available"

            if end_hour > BookingRules.CLOSE_HOUR:
                status = "unavailable"

            if status == "available" and is_today and start_hour <= now.hour:
                status = "unavailable"

            if status == "available" and overlaps(start_hour, end_hour, blocked_intervals):
                status = "unavailable"

            if status == "available":
                has_available_option = True

            options.append(
                {
                    "duration_hours": duration,
                    "start_hour": start_hour,
                    "end_hour": end_hour,
                    "start_label": format_hour(start_hour),
                    "end_label": format_hour(end_hour),
                    "label": f"{format_hour(start_hour)} - {format_hour(end_hour)}",
                    "status": status,
                }
            )

        slot_rows.append(
            {
                "start_hour": start_hour,
                "start_label": format_hour(start_hour),
                "status": "available" if has_available_option else "unavailable",
                "options": options,
            }
        )

    return slot_rows


def build_availability_map(court_rows, sport_rows, selected_date):
    availability_map = {}

    for court_row in court_rows:
        court_id = str(court_row["id"])
        blocked_intervals = load_blocked_intervals(court_row["id"], selected_date)
        base_slot_rows = build_slot_matrix(selected_date, blocked_intervals)

        per_sport = {}
        for sport_row in sport_rows:
            per_sport[str(sport_row["id"])] = base_slot_rows

        availability_map[court_id] = per_sport
    return availability_map


class BookingView(View):
    @staticmethod
    def get(request):
        selected_date = parse_selected_date(request.GET.get("date"))

        court_rows = list(courts.objects.values("id", "name", "description"))
        sport_rows = list(sports.objects.values("id", "name"))
        if not sport_rows:
            sport_rows = [
                {"id": 1, "name": "VÃ´lei"},
                {"id": 2, "name": "FutevÃ´lei"},
                {"id": 3, "name": "Beach TÃªnnis"},
            ]

        availability_map = build_availability_map(court_rows, sport_rows, selected_date)
        context = {
            "today_iso": timezone.localdate().isoformat(),
            "selected_date_iso": selected_date.isoformat(),
            "selected_date_display": selected_date.strftime("%d/%m/%Y"),
            "courts": court_rows,
            "sports": sport_rows,
            "availability_map": availability_map,
        }
        return render(request, "booking.html", context)


class BookingConfirmView(View):
    @staticmethod
    def _has_conflict(payload):
        return schedules.objects.filter(
            court_id=payload["court_obj"],
            date=payload["selected_date"],
            is_active=True,
            start_hour__lt=time(hour=payload["end_hour"]),
            end_hour__gt=time(hour=payload["start_hour"]),
        ).exists()

    @staticmethod
    def _parse_booking_payload(source, validate_slot=True):
        court_id = source.get("court")
        date_iso = source.get("date")
        sport_id = source.get("sport")
        start_time = source.get("start_time")
        end_time = source.get("end_time")

        try:
            court_id = int(court_id)
            sport_id = int(sport_id)
        except (TypeError, ValueError):
            return None

        if not date_iso or not start_time or not end_time:
            return None

        selected_date = parse_selected_date(date_iso)

        try:
            start_hour = datetime.strptime(start_time, "%H:%M").time().hour
            end_hour = datetime.strptime(end_time, "%H:%M").time().hour
        except ValueError:
            return None

        if end_hour <= start_hour or end_hour - start_hour > BookingRules.MAX_DURATION_HOURS:
            return None

        court_obj = courts.objects.filter(id=court_id).first()
        if not court_obj:
            return None

        sport_obj = sports.objects.filter(id=sport_id).first()
        if not sport_obj:
            return None

        if validate_slot:
            blocked_intervals = load_blocked_intervals(court_id, selected_date)
            matrix = build_slot_matrix(selected_date, blocked_intervals)
            is_valid_slot = any(
                row["start_hour"] == start_hour
                and any(
                    option["start_hour"] == start_hour
                    and option["end_hour"] == end_hour
                    and option["status"] == "available"
                    for option in row["options"]
                )
                for row in matrix
            )

            if not is_valid_slot:
                return None

        return {
            "court_id": court_id,
            "sport_id": sport_id,
            "date_iso": selected_date.isoformat(),
            "selected_date": selected_date,
            "start_hour": start_hour,
            "end_hour": end_hour,
            "court_obj": court_obj,
            "sport_obj": sport_obj,
        }

    @staticmethod
    def _build_context(payload, guest_name="", guest_phone="", form_error="", booking_warning=""):
        booking_price = booking_total_price(
            payload["selected_date"],
            payload["start_hour"],
            payload["end_hour"],
        )
        return {
            "selected_date_display": payload["selected_date"].strftime("%d/%m/%Y"),
            "selected_date_iso": payload["date_iso"],
            "selected_court_id": payload["court_id"],
            "selected_sport_id": payload["sport_id"],
            "selected_court_name": payload["court_obj"].name,
            "selected_sport_name": payload["sport_obj"].name,
            "selected_start_time": format_hour(payload["start_hour"]),
            "selected_end_time": format_hour(payload["end_hour"]),
            "booking_price_display": format_price_brl(booking_price),
            "guest_name": guest_name,
            "guest_phone": guest_phone,
            "form_error": form_error,
            "booking_warning": booking_warning,
            "success_message": "",
            "success_redirect_url": "",
        }

    @staticmethod
    def get(request):
        payload = BookingConfirmView._parse_booking_payload(request.GET)
        if not payload:
            return redirect("booking")

        context = BookingConfirmView._build_context(payload)
        return render(request, "booking-confirm.html", context)

    @staticmethod
    def post(request):
        payload = BookingConfirmView._parse_booking_payload(request.POST, validate_slot=False)
        if not payload:
            messages.error(request, "Horário inválido ou indisponível. Escolha outro horário.")
            return redirect("booking")

        if request.user.is_authenticated:
            schedule_user = request.user
            schedule_name = schedule_user.name
            schedule_phone = schedule_user.phone
        else:
            schedule_user = None
            schedule_name = request.POST.get("guest_name", "").strip()
            guest_phone = request.POST.get("guest_phone", "").strip()
            schedule_phone_digits = "".join(char for char in guest_phone if char.isdigit())

            if not schedule_name or not schedule_phone_digits:
                context = BookingConfirmView._build_context(
                    payload,
                    guest_name=schedule_name,
                    guest_phone=guest_phone,
                    form_error="Preencha nome e telefone para continuar.",
                )
                return render(request, "booking-confirm.html", context)

            schedule_phone = int(schedule_phone_digits)

        if BookingConfirmView._has_conflict(payload):
            context = BookingConfirmView._build_context(
                payload,
                guest_name=schedule_name,
                guest_phone=request.POST.get("guest_phone", "").strip(),
                booking_warning="Este horÃ¡rio para a quadra selecionada nÃ£o estÃ¡ mais disponÃ­vel. Verifique a disponibilidade atual atravÃ©s do botÃ£o abaixo.",
            )
            return render(request, "booking-confirm.html", context)

        schedules.objects.create(
            date=payload["selected_date"],
            start_hour=time(hour=payload["start_hour"]),
            end_hour=time(hour=payload["end_hour"]),
            user_id=schedule_user,
            court_id=payload["court_obj"],
            sport_id=payload["sport_obj"],
            user_name=schedule_name,
            user_phone=schedule_phone,
        )

        success_redirect_url = reverse("my_bookings") if request.user.is_authenticated else reverse("menu")
        context = BookingConfirmView._build_context(payload)
        context["success_message"] = "Agendamento confirmado com sucesso."
        context["success_redirect_url"] = success_redirect_url
        return render(request, "booking-confirm.html", context)


class MyBookingsView(View):
    @staticmethod
    def _attach_price_display(rows):
        for row in rows:
            start_hour = row.start_hour.hour
            end_hour = row.end_hour.hour
            row.booking_price_display = format_price_brl(
                booking_total_price(row.date, start_hour, end_hour)
            )
        return rows

    @staticmethod
    def _attach_cancellation_rules(rows, user):
        now = timezone.localtime()

        for row in rows:
            row.can_cancel = user_can_cancel_booking(user, row, now=now)
            row.cancel_block_reason = ""
            if not row.can_cancel:
                row.cancel_block_reason = "O cancelamento fica disponÃ­vel somente atÃ© 1 hora antes do horÃ¡rio agendado."

        return rows

    @staticmethod
    def _context_for_user(request):
        now = timezone.localtime()
        today = now.date()
        current_time = now.time().replace(microsecond=0)

        current_filter = Q(date__gt=today) | Q(date=today, end_hour__gt=current_time)
        past_filter = Q(date__lt=today) | Q(date=today, end_hour__lte=current_time)

        base_queryset = schedules.objects.filter(user_id=request.user).select_related("court_id", "sport_id")

        current_rows = list(
            base_queryset.filter(is_active=True).filter(current_filter).order_by("date", "start_hour")
        )
        past_rows = list(
            base_queryset.filter(Q(is_active=False) | past_filter).order_by("-date", "-start_hour")
        )

        current_rows = MyBookingsView._attach_price_display(current_rows)
        current_rows = MyBookingsView._attach_cancellation_rules(current_rows, request.user)
        past_rows = MyBookingsView._attach_price_display(past_rows)

        return {
            "current_bookings": current_rows,
            "past_bookings": past_rows,
        }

    @staticmethod
    def get(request):
        if not request.user.is_authenticated:
            return redirect("login")

        context = MyBookingsView._context_for_user(request)
        return render(request, "my-bookings.html", context)

    @staticmethod
    def post(request):
        if not request.user.is_authenticated:
            return redirect("login")

        schedule_id = request.POST.get("schedule_id")
        try:
            schedule_id = int(schedule_id)
        except (TypeError, ValueError):
            messages.error(request, "Agendamento inválido.")
            return redirect("my_bookings")

        booking = schedules.objects.filter(
            id=schedule_id,
            user_id=request.user,
            is_active=True,
        ).first()

        if not booking:
            messages.error(request, "Não foi possível cancelar esse agendamento.")
            return redirect("my_bookings")

        if not user_can_cancel_booking(request.user, booking):
            messages.error(request, "O cancelamento so pode ser feito até 1 hora antes do horário agendado.")
            return redirect("my_bookings")

        booking.is_active = False
        booking.cancelled_at = timezone.now()
        booking.save(update_fields=["is_active", "cancelled_at", "updated_at"])

        messages.success(request, "Horário cancelado com sucesso.")
        context = MyBookingsView._context_for_user(request)
        return render(request, "my-bookings.html", context)


class AdminBookingsView(View):
    @staticmethod
    def _user_is_admin(request):
        return request.user.is_authenticated and getattr(request.user, "is_admin", False)

    @staticmethod
    def _attach_price_display(rows):
        for row in rows:
            start_hour = row.start_hour.hour
            end_hour = row.end_hour.hour
            row.booking_price_display = format_price_brl(
                booking_total_price(row.date, start_hour, end_hour)
            )
        return rows

    @staticmethod
    def _attach_customer_display(rows):
        for row in rows:
            if row.user_name:
                row.customer_display = row.user_name
                row.phone_display = row.user_phone
            elif row.user_id:
                row.customer_display = row.user_id.name
                row.phone_display = row.user_id.phone
            else:
                row.customer_display = "NÃ£o informado"
        return rows

    @staticmethod
    def _attach_phone_display(rows):
        for row in rows:
            if row.user_phone:
                row.phone_display = row.user_phone
            elif row.user_id:
                row.phone_display = row.user_id.phone
            else:
                row.phone_display = "NÃ£o informado"
        return rows

    @staticmethod
    def _parse_optional_int(value):
        try:
            parsed = int(value)
            if parsed <= 0:
                return None
            return parsed
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _apply_sport_and_court_filters(queryset, sport_id=None, court_id=None):
        filtered = queryset
        if sport_id:
            filtered = filtered.filter(sport_id_id=sport_id)
        if court_id:
            filtered = filtered.filter(court_id_id=court_id)
        return filtered

    @staticmethod
    def _apply_customer_filter(queryset, customer_name=""):
        normalized_name = (customer_name or "").strip()
        if not normalized_name:
            return queryset
        return queryset.filter(
            Q(user_name__icontains=normalized_name) | Q(user_id__name__icontains=normalized_name)
        )

    @staticmethod
    def _normalize_tab(tab_value):
        if tab_value == "past":
            return "past"
        return "current"

    @staticmethod
    def _parse_time_value(raw_time):
        if not raw_time:
            return None
        try:
            return datetime.strptime(raw_time, "%H:%M").time()
        except ValueError:
            return None

    @staticmethod
    def _list_active_blocks(selected_date, court_id=None):
        queryset = active_block_queryset_for_date(selected_date).select_related("court_id")
        if court_id:
            queryset = queryset.filter(court_id_id=court_id)

        rows = list(queryset.order_by("start_at"))
        for row in rows:
            local_start = timezone.localtime(row.start_at)
            local_end = timezone.localtime(row.end_at)
            row.block_date_display = selected_date.strftime("%d/%m/%Y")
            row.start_hour_display = local_start.strftime("%H:%M")
            row.end_hour_display = local_end.strftime("%H:%M")
            row.fixed_label = ""
            if row.is_fixed and row.fixed_weekday is not None:
                row.fixed_label = f"Fixo toda {weekday_label(row.fixed_weekday)}"
        return rows

    @staticmethod
    def _build_redirect_url(selected_date, sport_id=None, court_id=None, selected_tab="current", customer_name="", customer_phone=""):
        query_params = {
            "date": selected_date.isoformat(),
            "sport": sport_id or "",
            "court": court_id or "",
            "tab": AdminBookingsView._normalize_tab(selected_tab),
            "customer": (customer_name or "").strip(),
            "phone_number": (customer_phone or "").strip(),
        }
        return f"{reverse('admin_bookings')}?{urlencode(query_params)}"

    @staticmethod
    def _context(selected_date, sport_id=None, court_id=None, selected_tab="current", customer_name="", customer_phone=""):
        now = timezone.localtime()
        today = now.date()
        current_time = now.time().replace(microsecond=0)
        normalized_tab = AdminBookingsView._normalize_tab(selected_tab)

        current_filter = Q(date__gt=today) | Q(date=today, end_hour__gt=current_time)
        past_filter = Q(date__lt=today) | Q(date=today, end_hour__lte=current_time)

        base_queryset = schedules.objects.select_related("court_id", "sport_id", "user_id")
        selected_date_queryset = base_queryset.filter(date=selected_date)
        selected_date_queryset = AdminBookingsView._apply_sport_and_court_filters(
            selected_date_queryset, sport_id=sport_id, court_id=court_id
        )
        selected_date_queryset = AdminBookingsView._apply_customer_filter(
            selected_date_queryset, customer_name=customer_name
        )
        past_queryset = AdminBookingsView._apply_sport_and_court_filters(
            base_queryset, sport_id=sport_id, court_id=court_id
        )
        past_queryset = AdminBookingsView._apply_customer_filter(
            past_queryset, customer_name=customer_name
        )

        current_rows = []
        past_rows = []

        # Lazy-load: query only the tab that is currently selected.
        if normalized_tab == "current":
            current_rows = list(
                selected_date_queryset.filter(is_active=True).filter(current_filter).order_by("date", "start_hour")
            )
        else:
            past_rows = list(
                past_queryset.filter(Q(is_active=False) | past_filter).order_by("-date", "-start_hour")
            )

        current_rows = AdminBookingsView._attach_price_display(current_rows)
        past_rows = AdminBookingsView._attach_price_display(past_rows)
        current_rows = AdminBookingsView._attach_customer_display(current_rows)
        past_rows = AdminBookingsView._attach_customer_display(past_rows)
        current_rows = AdminBookingsView._attach_phone_display(current_rows)
        past_rows = AdminBookingsView._attach_phone_display(past_rows)

        return {
            "current_bookings": current_rows,
            "past_bookings": past_rows,
            "active_blocks": AdminBookingsView._list_active_blocks(selected_date, court_id=court_id),
            "selected_date_iso": selected_date.isoformat(),
            "selected_date_display": selected_date.strftime("%d/%m/%Y"),
            "sports": sports.objects.values("id", "name").order_by("name"),
            "courts": courts.objects.values("id", "name").order_by("name"),
            "selected_sport_id": sport_id or "",
            "selected_court_id": court_id or "",
            "selected_tab": normalized_tab,
            "selected_customer_name": (customer_name or "").strip(),
            "selected_customer_phone": (customer_phone or "").strip(),
        }

    @staticmethod
    def get(request):
        if not request.user.is_authenticated:
            return redirect("login")

        if not AdminBookingsView._user_is_admin(request):
            messages.error(request, "Acesso restrito a administradores.")
            return redirect("menu")

        selected_date = parse_selected_date(request.GET.get("date"))
        selected_sport_id = AdminBookingsView._parse_optional_int(request.GET.get("sport"))
        selected_court_id = AdminBookingsView._parse_optional_int(request.GET.get("court"))
        selected_tab = AdminBookingsView._normalize_tab(request.GET.get("tab"))
        customer_name = request.GET.get("customer", "")
        customer_phone = request.GET.get("phone_number", "")
        context = AdminBookingsView._context(
            selected_date,
            sport_id=selected_sport_id,
            court_id=selected_court_id,
            selected_tab=selected_tab,
            customer_name=customer_name,
            customer_phone=customer_phone,
        )
        return render(request, "admin-bookings.html", context)

    @staticmethod
    def post(request):
        if not request.user.is_authenticated:
            return redirect("login")

        if not AdminBookingsView._user_is_admin(request):
            messages.error(request, "Acesso restrito a administradores.")
            return redirect("menu")

        selected_date = parse_selected_date(request.POST.get("date"))
        selected_sport_id = AdminBookingsView._parse_optional_int(request.POST.get("sport"))
        selected_court_id = AdminBookingsView._parse_optional_int(request.POST.get("court"))
        selected_tab = AdminBookingsView._normalize_tab(request.POST.get("tab"))
        customer_name = request.POST.get("customer", "")
        customer_phone = request.POST.get("phone_number", "")
        action = request.POST.get("action", "cancel_booking")

        if action == "create_block":
            block_court_id = AdminBookingsView._parse_optional_int(request.POST.get("block_court_id"))
            block_date = parse_selected_date(request.POST.get("block_date"))
            block_start_time = AdminBookingsView._parse_time_value(request.POST.get("block_start_time"))
            block_end_time = AdminBookingsView._parse_time_value(request.POST.get("block_end_time"))
            block_reason = (request.POST.get("block_reason") or "").strip() or "Bloqueio administrativo"

            if not block_court_id or not block_start_time or not block_end_time:
                messages.error(request, "Preencha quadra, horário inicial e horário final para bloquear.")
                return redirect(
                    AdminBookingsView._build_redirect_url(
                        selected_date,
                        sport_id=selected_sport_id,
                        court_id=selected_court_id,
                        selected_tab=selected_tab,
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                    )
                )

            if block_end_time <= block_start_time:
                messages.error(request, "O horário final deve ser maior que o horário inicial.")
                return redirect(
                    AdminBookingsView._build_redirect_url(
                        block_date,
                        sport_id=selected_sport_id,
                        court_id=selected_court_id,
                        selected_tab=selected_tab,
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                    )
                )

            start_at = timezone.make_aware(datetime.combine(block_date, block_start_time), timezone.get_current_timezone())
            end_at = timezone.make_aware(datetime.combine(block_date, block_end_time), timezone.get_current_timezone())

            has_schedule_conflict = schedules.objects.filter(
                court_id_id=block_court_id,
                date=block_date,
                is_active=True,
                start_hour__lt=block_end_time,
                end_hour__gt=block_start_time,
            ).exists()
            if has_schedule_conflict:
                messages.error(request, "Já existe agendamento ativo no intervalo informado.")
                return redirect(
                    AdminBookingsView._build_redirect_url(
                        block_date,
                        sport_id=selected_sport_id,
                        court_id=selected_court_id,
                        selected_tab=selected_tab,
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                    )
                )

            has_block_conflict = court_blocks.objects.filter(
                court_id_id=block_court_id,
                is_active=True,
                start_at__lt=end_at,
                end_at__gt=start_at,
            ).exists()
            if has_block_conflict:
                messages.error(request, "Já existe bloqueio ativo no intervalo informado.")
                return redirect(
                    AdminBookingsView._build_redirect_url(
                        block_date,
                        sport_id=selected_sport_id,
                        court_id=selected_court_id,
                        selected_tab=selected_tab,
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                    )
                )

            court_blocks.objects.create(
                court_id_id=block_court_id,
                start_at=start_at,
                end_at=end_at,
                reason=block_reason,
                is_active=True,
            )
            messages.success(request, "Horário bloqueado com sucesso.")
            return redirect(
                AdminBookingsView._build_redirect_url(
                    block_date,
                    sport_id=selected_sport_id,
                    court_id=selected_court_id,
                    selected_tab=selected_tab,
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                )
            )

        if action == "remove_block":
            block_id = request.POST.get("block_id")
            block_cancel_scope = request.POST.get("block_cancel_scope", "permanent")
            try:
                block_id = int(block_id)
            except (TypeError, ValueError):
                messages.error(request, "Bloqueio inválido.")
                return redirect(
                    AdminBookingsView._build_redirect_url(
                        selected_date,
                        sport_id=selected_sport_id,
                        court_id=selected_court_id,
                        selected_tab=selected_tab,
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                    )
                )

            block = court_blocks.objects.filter(id=block_id, is_active=True).first()
            if not block:
                messages.error(request, "Bloqueio não encontrado.")
                return redirect(
                    AdminBookingsView._build_redirect_url(
                        selected_date,
                        sport_id=selected_sport_id,
                        court_id=selected_court_id,
                        selected_tab=selected_tab,
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                    )
                )

            if block.is_fixed and block_cancel_scope == "this_week":
                court_block_exceptions.objects.get_or_create(
                    block_id=block,
                    skip_date=selected_date,
                )
                messages.success(request, "Bloqueio fixo cancelado apenas para esta semana.")
                return redirect(
                    AdminBookingsView._build_redirect_url(
                        selected_date,
                        sport_id=selected_sport_id,
                        court_id=selected_court_id,
                        selected_tab=selected_tab,
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                    )
                )

            block.is_active = False
            block.cancelled_at = timezone.now()
            block.save(update_fields=["is_active", "cancelled_at", "updated_at"])
            if block.is_fixed:
                messages.success(request, "Bloqueio fixo cancelado definitivamente.")
            else:
                messages.success(request, "Bloqueio cancelado com sucesso.")
            return redirect(
                AdminBookingsView._build_redirect_url(
                    selected_date,
                    sport_id=selected_sport_id,
                    court_id=selected_court_id,
                    selected_tab=selected_tab,
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                )
            )

        schedule_id = request.POST.get("schedule_id")
        try:
            schedule_id = int(schedule_id)
        except (TypeError, ValueError):
            messages.error(request, "Agendamento inválido.")
            return redirect(
                AdminBookingsView._build_redirect_url(
                    selected_date,
                    sport_id=selected_sport_id,
                    court_id=selected_court_id,
                    selected_tab=selected_tab,
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                )
            )

        booking = schedules.objects.filter(
            id=schedule_id,
            is_active=True,
        ).first()

        if not booking:
            messages.error(request, "Não foi possível cancelar esse agendamento.")
            return redirect(
                AdminBookingsView._build_redirect_url(
                    selected_date,
                    sport_id=selected_sport_id,
                    court_id=selected_court_id,
                    selected_tab=selected_tab,
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                )
            )

        booking.is_active = False
        booking.cancelled_at = timezone.now()
        booking.save(update_fields=["is_active", "cancelled_at", "updated_at"])

        messages.success(request, "Horário cancelado com sucesso.")
        context = AdminBookingsView._context(
            selected_date,
            sport_id=selected_sport_id,
            court_id=selected_court_id,
            selected_tab=selected_tab,
            customer_name=customer_name,
            customer_phone=customer_phone,
        )
        return render(request, "admin-bookings.html", context)


class AdminBlocksView(View):
    @staticmethod
    def _build_redirect_url(selected_date, court_id=None):
        query_params = {
            "date": selected_date.isoformat(),
            "court": court_id or "",
        }
        return f"{reverse('admin_blocks')}?{urlencode(query_params)}"

    @staticmethod
    def _context(selected_date, selected_court_id=None):
        return {
            "selected_date_iso": selected_date.isoformat(),
            "selected_date_display": selected_date.strftime("%d/%m/%Y"),
            "selected_court_id": selected_court_id or "",
            "courts": courts.objects.values("id", "name").order_by("name"),
            "active_blocks": AdminBookingsView._list_active_blocks(selected_date, court_id=selected_court_id),
        }

    @staticmethod
    def get(request):
        if not request.user.is_authenticated:
            return redirect("login")

        if not AdminBookingsView._user_is_admin(request):
            messages.error(request, "Acesso restrito a administradores.")
            return redirect("menu")

        selected_date = parse_selected_date(request.GET.get("date"))
        selected_court_id = AdminBookingsView._parse_optional_int(request.GET.get("court"))
        context = AdminBlocksView._context(selected_date, selected_court_id=selected_court_id)
        return render(request, "admin-blocks.html", context)

    @staticmethod
    def post(request):
        if not request.user.is_authenticated:
            return redirect("login")

        if not AdminBookingsView._user_is_admin(request):
            messages.error(request, "Acesso restrito a administradores.")
            return redirect("menu")

        selected_date = parse_selected_date(request.POST.get("date"))
        selected_court_id = AdminBookingsView._parse_optional_int(request.POST.get("court"))
        action = request.POST.get("action", "create_block")

        if action == "remove_block":
            block_id = request.POST.get("block_id")
            try:
                block_id = int(block_id)
            except (TypeError, ValueError):
                messages.error(request, "Bloqueio inválido.")
                return redirect(AdminBlocksView._build_redirect_url(selected_date, court_id=selected_court_id))

            block = court_blocks.objects.filter(id=block_id, is_active=True).first()
            if not block:
                messages.error(request, "Bloqueio não encontrado.")
                return redirect(AdminBlocksView._build_redirect_url(selected_date, court_id=selected_court_id))

            block_date = timezone.localtime(block.start_at).date()
            block.is_active = False
            block.cancelled_at = timezone.now()
            block.save(update_fields=["is_active", "cancelled_at", "updated_at"])
            messages.success(request, "Bloqueio cancelado com sucesso.")
            return redirect(AdminBlocksView._build_redirect_url(block_date, court_id=selected_court_id))

        raw_block_court_id = (request.POST.get("block_court_id") or "").strip()
        block_court_id = AdminBookingsView._parse_optional_int(raw_block_court_id)
        apply_to_all_courts = raw_block_court_id == "all"
        block_date = parse_selected_date(request.POST.get("block_date"))
        block_start_time = AdminBookingsView._parse_time_value(request.POST.get("block_start_time"))
        block_end_time = AdminBookingsView._parse_time_value(request.POST.get("block_end_time"))
        block_reason = (request.POST.get("block_reason") or "").strip() or "Bloqueio administrativo"
        is_fixed = request.POST.get("block_is_fixed") == "true"

        if (not block_court_id and not apply_to_all_courts):
            messages.error(request, "Preencha a quadra para bloquear.")
            return redirect(AdminBlocksView._build_redirect_url(selected_date, court_id=selected_court_id))

        # If no time range is provided, block the entire selected day.
        if not block_start_time and not block_end_time:
            block_start_time = time(hour=0, minute=0)
            block_end_time = time(hour=23, minute=59)
        elif (block_start_time and not block_end_time) or (block_end_time and not block_start_time):
            messages.error(request, "Informe os dois horários ou deixe ambos vazios para bloquear o dia todo.")
            return redirect(AdminBlocksView._build_redirect_url(selected_date, court_id=selected_court_id))

        if block_end_time <= block_start_time:
            messages.error(request, "O horário final deve ser maior que o horário inicial.")
            return redirect(AdminBlocksView._build_redirect_url(block_date, court_id=selected_court_id))

        start_at = timezone.make_aware(datetime.combine(block_date, block_start_time), timezone.get_current_timezone())
        end_at = timezone.make_aware(datetime.combine(block_date, block_end_time), timezone.get_current_timezone())
        block_weekday = block_date.weekday()
        django_weekday = python_weekday_to_django(block_weekday)

        target_court_ids = []
        if apply_to_all_courts:
            target_court_ids = list(courts.objects.values_list("id", flat=True))
        elif block_court_id:
            target_court_ids = [block_court_id]

        if not target_court_ids:
            messages.error(request, "Nenhuma quadra disponível para bloqueio.")
            return redirect(AdminBlocksView._build_redirect_url(block_date, court_id=selected_court_id))

        schedule_conflict_filter = Q(
            court_id_id__in=target_court_ids,
            is_active=True,
            start_hour__lt=block_end_time,
            end_hour__gt=block_start_time,
        )
        if is_fixed:
            schedule_conflict_filter &= Q(date__gte=block_date, date__week_day=django_weekday)
        else:
            schedule_conflict_filter &= Q(date=block_date)

        has_schedule_conflict = schedules.objects.filter(schedule_conflict_filter).exists()
        if has_schedule_conflict:
            if apply_to_all_courts:
                messages.error(request, "Existe agendamento ativo em pelo menos uma quadra no intervalo informado.")
            else:
                messages.error(request, "Existe agendamento ativo na quadra no intervalo informado.")
            return redirect(AdminBlocksView._build_redirect_url(block_date, court_id=selected_court_id))

        block_conflict_filter = Q(
            court_id_id__in=target_court_ids,
            is_active=True,
            start_at__lt=end_at,
            end_at__gt=start_at,
        )
        if is_fixed:
            block_conflict_filter &= (
                Q(is_fixed=True, fixed_weekday=block_weekday)
                | Q(start_at__date__gte=block_date, start_at__week_day=django_weekday)
            )
        else:
            block_conflict_filter &= (
                Q(start_at__date=block_date)
                | Q(is_fixed=True, fixed_weekday=block_weekday, start_at__date__lte=block_date)
            )

        has_block_conflict = court_blocks.objects.filter(block_conflict_filter).exists()
        if has_block_conflict:
            if apply_to_all_courts:
                messages.error(request, "Já existe bloqueio ativo em pelo menos uma quadra no intervalo informado.")
            else:
                messages.error(request, "Já existe bloqueio ativo no intervalo informado.")
            return redirect(AdminBlocksView._build_redirect_url(block_date, court_id=selected_court_id))

        block_rows = [
            court_blocks(
                court_id_id=court_id,
                start_at=start_at,
                end_at=end_at,
                reason=block_reason,
                is_fixed=is_fixed,
                fixed_weekday=block_weekday if is_fixed else None,
                is_active=True,
            )
            for court_id in target_court_ids
        ]
        with transaction.atomic():
            court_blocks.objects.bulk_create(block_rows)

        if apply_to_all_courts:
            if is_fixed:
                messages.success(request, "Bloqueios fixos criados com sucesso.")
            else:
                messages.success(request, "Horários bloqueados com sucesso.")
        else:
            if is_fixed:
                messages.success(request, "Bloqueio fixo criado com sucesso.")
            else:
                messages.success(request, "Horário bloqueado com sucesso.")
        return redirect(AdminBlocksView._build_redirect_url(block_date, court_id=selected_court_id))

