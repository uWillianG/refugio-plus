from datetime import date, datetime, time
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Q
from django.urls import reverse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from booking.models import courts, holidays, schedules, sports


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


def resolve_block_model():
    return None


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
        pass

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
                {"id": 1, "name": "Vôlei"},
                {"id": 2, "name": "Futevôlei"},
                {"id": 3, "name": "Beach Tênnis"},
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
    def _parse_booking_payload(source):
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
    def _build_context(payload, guest_name="", guest_phone="", form_error=""):
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
        payload = BookingConfirmView._parse_booking_payload(request.POST)
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

        return {
            "current_bookings": MyBookingsView._attach_price_display(current_rows),
            "past_bookings": MyBookingsView._attach_price_display(past_rows),
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
                row.customer_display = "Não informado"
        return rows

    @staticmethod
    def _attach_phone_display(rows):
        for row in rows:
            if row.user_phone:
                row.phone_display = row.user_phone
            elif row.user_id:
                row.phone_display = row.user_id.phone
            else:
                row.phone_display = "Não informado"
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
