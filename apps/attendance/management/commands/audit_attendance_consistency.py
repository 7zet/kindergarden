from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.attendance.models import Attendance, CheckEvent, Status


class Command(BaseCommand):
    help = "CheckEvent va Attendance o'rtasidagi nomuvofiqliklarni tekshiradi"

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true",
                            help="Eventdan kunlik xulosani deterministik tiklaydi")

    @transaction.atomic
    def handle(self, *args, **options):
        problems = fixed = 0
        pairs = (CheckEvent.objects.values_list("enrollment_id", "occurred_at")
                 .iterator())
        seen = set()
        for enrollment_id, occurred_at in pairs:
            day = timezone.localtime(occurred_at).date()
            key = (enrollment_id, day)
            if key in seen:
                continue
            seen.add(key)
            events = CheckEvent.objects.filter(enrollment_id=enrollment_id)
            daily = [e for e in events if timezone.localtime(e.occurred_at).date() == day]
            ins = sorted((e for e in daily if e.kind == CheckEvent.Kind.IN), key=lambda e: e.occurred_at)
            outs = sorted((e for e in daily if e.kind == CheckEvent.Kind.OUT), key=lambda e: e.occurred_at)
            mark = Attendance.objects.filter(enrollment_id=enrollment_id, day=day).first()
            expected_in = timezone.localtime(ins[0].occurred_at).time().replace(microsecond=0) if ins else None
            expected_out = timezone.localtime(outs[-1].occurred_at).time().replace(microsecond=0) if outs else None
            bad = bool(ins and (not mark or mark.status != Status.PRESENT or mark.arrived_at != expected_in))
            bad = bad or bool(outs and (not mark or mark.left_at != expected_out))
            if not bad:
                continue
            problems += 1
            self.stdout.write(f"NOMUVOFIQ enrollment={enrollment_id} day={day}")
            if options["fix"] and ins:
                first = ins[0]
                Attendance.objects.update_or_create(
                    enrollment_id=enrollment_id, day=day,
                    defaults={"status": Status.PRESENT, "reason": "",
                              "arrived_at": expected_in, "left_at": expected_out,
                              "marked_by": first.recorded_by},
                )
                fixed += 1
        self.stdout.write(self.style.SUCCESS(
            f"Tekshirildi: {len(seen)} kun; nomuvofiq: {problems}; tuzatildi: {fixed}"
        ))
