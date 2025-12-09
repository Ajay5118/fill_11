from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
import uuid

# Import from users app
from apps.users.models import User, Team, BaseModel, PlayerRole


# ==================== ENUMS ====================

class VenueType(models.TextChoices):
    BOX_CRICKET = 'BOX_CRICKET', 'Box Cricket'
    PAID_OPEN = 'PAID_OPEN', 'Paid Open'
    FREE_LOCAL = 'FREE_LOCAL', 'Free Local'

class BookingMode(models.TextChoices):
    IN_APP_PAY = 'IN_APP_PAY', 'In-App Payment'
    RECEIPT_UPLOAD = 'RECEIPT_UPLOAD', 'Receipt Upload'
    GPS_CHECKIN = 'GPS_CHECKIN', 'GPS Check-in'

class MatchType(models.TextChoices):
    SOLO_MIX = 'SOLO_MIX', 'Solo Mix'
    TEAM_VS_TEAM = 'TEAM_VS_TEAM', 'Team vs Team'

class GroundStatus(models.TextChoices):
    BOOKED = 'BOOKED', 'Booked'
    SECURED = 'SECURED', 'Secured'
    UNSECURED = 'UNSECURED', 'Unsecured'

class VacancyStatus(models.TextChoices):
    OPEN = 'OPEN', 'Open'
    FILLED = 'FILLED', 'Filled'
    EXPIRED = 'EXPIRED', 'Expired'

class PaymentStatus(models.TextChoices):
    HELD = 'HELD', 'Held'
    RELEASED = 'RELEASED', 'Released'
    REFUNDED = 'REFUNDED', 'Refunded'

# ==================== MODELS ====================

class Venue(BaseModel):
    venue_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    name = models.CharField(max_length=255)
    venue_type = models.CharField(
        max_length=20,
        choices=VenueType.choices
    )
    booking_mode = models.CharField(
        max_length=20,
        choices=BookingMode.choices
    )
    is_verified = models.BooleanField(default=False)
    gps_lat = models.FloatField(
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)]
    )
    gps_long = models.FloatField(
        validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)]
    )
    avg_cost_per_hour = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Average cost in local currency"
    )
    address = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'venues'
        verbose_name = 'Venue'
        verbose_name_plural = 'Venues'
        indexes = [
            models.Index(fields=['venue_type']),
            models.Index(fields=['is_verified']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_venue_type_display()})"


class Match(BaseModel):
    match_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    host_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='hosted_matches'
    )
    visitor_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        related_name='visiting_matches',
        blank=True,
        null=True
    )
    venue = models.ForeignKey(
        Venue,
        on_delete=models.PROTECT,
        related_name='matches'
    )
    match_type = models.CharField(
        max_length=20,
        choices=MatchType.choices
    )
    ground_status = models.CharField(
        max_length=20,
        choices=GroundStatus.choices,
        default=GroundStatus.UNSECURED
    )
    start_time = models.DateTimeField()
    total_slots = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(22)],
        help_text="Total player slots available"
    )
    is_cancelled = models.BooleanField(default=False)

    class Meta:
        db_table = 'matches'
        verbose_name = 'Match'
        verbose_name_plural = 'Matches'
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['start_time']),
            models.Index(fields=['match_type']),
            models.Index(fields=['ground_status']),
        ]

    def __str__(self):
        return f"Match at {self.venue.name} on {self.start_time.strftime('%Y-%m-%d %H:%M') if self.start_time else 'TBD'}"

    def clean(self):
        if self.start_time and self.start_time < timezone.now():
            raise ValidationError("Match start time cannot be in the past")

    @property
    def is_upcoming(self):
        if not self.start_time:
            return False
        return self.start_time > timezone.now() and not self.is_cancelled


class Vacancy(BaseModel):
    vacancy_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name='vacancies'
    )
    looking_for_role = models.CharField(
        max_length=20,
        choices=PlayerRole.choices,
        default=PlayerRole.ANY
    )
    count_needed = models.IntegerField(
        validators=[MinValueValidator(1)]
    )
    cost_per_head = models.IntegerField(
        validators=[MinValueValidator(0)]
    )
    status = models.CharField(
        max_length=20,
        choices=VacancyStatus.choices,
        default=VacancyStatus.OPEN
    )
    filled_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )

    class Meta:
        db_table = 'vacancies'
        verbose_name = 'Vacancy'
        verbose_name_plural = 'Vacancies'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['match', 'status']),
        ]

    def __str__(self):
        return f"Vacancy for {self.count_needed} {self.get_looking_for_role_display()}(s) - {self.get_status_display()}"

    def clean(self):
        if self.filled_count > self.count_needed:
            raise ValidationError("Filled count cannot exceed count needed")

    def mark_as_filled(self):
        """Mark vacancy as filled"""
        if self.filled_count >= self.count_needed:
            self.status = VacancyStatus.FILLED
            self.save()


class GroundCheckin(BaseModel):
    checkin_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name='checkins'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='checkins'
    )
    checkin_time = models.DateTimeField(auto_now_add=True)
    user_lat = models.FloatField(
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)]
    )
    user_long = models.FloatField(
        validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)]
    )
    is_successful = models.BooleanField(default=False)
    distance_from_venue = models.FloatField(
        blank=True,
        null=True,
        help_text="Distance in meters"
    )

    class Meta:
        db_table = 'ground_checkins'
        verbose_name = 'Ground Check-in'
        verbose_name_plural = 'Ground Check-ins'
        unique_together = [['match', 'user']]
        indexes = [
            models.Index(fields=['match', 'user']),
            models.Index(fields=['checkin_time']),
        ]

    def __str__(self):
        return f"{self.user.full_name} checked in for match at {self.match.venue.name}"


class EscrowTransaction(BaseModel):
    escrow_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    match = models.ForeignKey(
        Match,
        on_delete=models.PROTECT,
        related_name='escrow_transactions'
    )
    payer = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='payments'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.HELD
    )
    release_condition = models.TextField(
        help_text="Condition for payment release"
    )
    released_at = models.DateTimeField(blank=True, null=True)
    refunded_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'escrow_transactions'
        verbose_name = 'Escrow Transaction'
        verbose_name_plural = 'Escrow Transactions'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['match', 'payer']),
        ]

    def __str__(self):
        return f"Escrow {self.amount} ({self.get_status_display()}) - {self.payer.full_name}"

    def release_payment(self):
        """Release the escrowed payment"""
        if self.status == PaymentStatus.HELD:
            self.status = PaymentStatus.RELEASED
            self.released_at = timezone.now()
            self.save()

    def refund_payment(self):
        """Refund the escrowed payment"""
        if self.status == PaymentStatus.HELD:
            self.status = PaymentStatus.REFUNDED
            self.refunded_at = timezone.now()
            self.save()