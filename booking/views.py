from datetime import date, datetime, time

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from booking.models import courts, holidays, schedules, sports


class BookingRules:
    WEEKDAY_OPEN_HOUR = 15
    WEEKEND_OPEN_HOUR = 8
    CLOSE_HOUR = 23
    MAX_DURATION_HOURS = 3
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


def parse_selected_date(raw_date):
    if not raw_date:
        return timezone.localdate()
    try:
        return date.fromisoformat(raw_date)
    except ValueError:
        return timezone.localdate()


def format_hour(hour_value):
    return f"{hour_value:02d}:00"


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
        return {
            "selected_date_display": payload["selected_date"].strftime("%d/%m/%Y"),
            "selected_date_iso": payload["date_iso"],
            "selected_court_id": payload["court_id"],
            "selected_sport_id": payload["sport_id"],
            "selected_court_name": payload["court_obj"].name,
            "selected_sport_name": payload["sport_obj"].name,
            "selected_start_time": format_hour(payload["start_hour"]),
            "selected_end_time": format_hour(payload["end_hour"]),
            "guest_name": guest_name,
            "guest_phone": guest_phone,
            "form_error": form_error,
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
            messages.error(request, "Horario invalido ou indisponivel. Escolha outro horario.")
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

        messages.success(request, "Agendamento confirmado com sucesso.")
        return redirect("booking")
