from django.contrib import admin
from .models import Venue, Match, Vacancy, GroundCheckin, EscrowTransaction


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    """Admin panel for Venue model"""
    list_display = [
        'name', 'venue_type', 'booking_mode', 'is_verified',
        'avg_cost_per_hour', 'created_at'
    ]

    list_filter = [
        'venue_type', 'booking_mode', 'is_verified', 'created_at'
    ]

    search_fields = ['name', 'address']

    readonly_fields = ['venue_id', 'created_at', 'updated_at']

    ordering = ['-created_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('venue_id', 'name', 'venue_type', 'booking_mode')
        }),
        ('Location Details', {
            'fields': ('gps_lat', 'gps_long', 'address')
        }),
        ('Pricing & Verification', {
            'fields': ('avg_cost_per_hour', 'is_verified')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    actions = ['mark_as_verified', 'mark_as_unverified']

    def mark_as_verified(self, request, queryset):
        """Mark selected venues as verified"""
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} venue(s) marked as verified.')

    mark_as_verified.short_description = "Mark selected venues as verified"

    def mark_as_unverified(self, request, queryset):
        """Mark selected venues as unverified"""
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} venue(s) marked as unverified.')

    mark_as_unverified.short_description = "Mark selected venues as unverified"


class VacancyInline(admin.TabularInline):
    """Inline admin for vacancies in Match admin"""
    model = Vacancy
    extra = 0
    readonly_fields = ['vacancy_id', 'filled_count', 'status']
    fields = [
        'looking_for_role', 'count_needed', 'filled_count',
        'cost_per_head', 'status'
    ]


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    """Admin panel for Match model"""
    list_display = [
        'match_id', 'get_host_captain', 'venue', 'match_type',
        'ground_status', 'start_time', 'total_slots', 'is_cancelled', 'created_at'
    ]

    list_filter = [
        'match_type', 'ground_status', 'is_cancelled',
        'start_time', 'created_at'
    ]

    search_fields = [
        'match_id', 'host_team__captain__full_name',
        'venue__name'
    ]

    readonly_fields = ['match_id', 'created_at', 'updated_at']

    ordering = ['-start_time']

    date_hierarchy = 'start_time'

    fieldsets = (
        ('Match Details', {
            'fields': ('match_id', 'match_type', 'ground_status', 'start_time', 'total_slots')
        }),
        ('Teams & Venue', {
            'fields': ('host_team', 'visitor_team', 'venue')
        }),
        ('Status', {
            'fields': ('is_cancelled',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    inlines = [VacancyInline]

    actions = ['cancel_matches', 'mark_ground_secured']

    def get_host_captain(self, obj):
        """Display host team captain name"""
        return obj.host_team.captain.full_name

    get_host_captain.short_description = 'Host Captain'
    get_host_captain.admin_order_field = 'host_team__captain__full_name'

    def is_upcoming(self, obj):
        """Show if match is upcoming"""
        return obj.is_upcoming

    is_upcoming.boolean = True
    is_upcoming.short_description = 'Upcoming'

    def cancel_matches(self, request, queryset):
        """Cancel selected matches"""
        from django.utils import timezone
        upcoming = queryset.filter(start_time__gt=timezone.now(), is_cancelled=False)
        updated = upcoming.update(is_cancelled=True)
        self.message_user(request, f'{updated} match(es) cancelled.')

    cancel_matches.short_description = "Cancel selected matches"

    def mark_ground_secured(self, request, queryset):
        """Mark ground as secured for selected matches"""
        updated = queryset.update(ground_status='SECURED')
        self.message_user(request, f'{updated} match(es) marked as secured.')

    mark_ground_secured.short_description = "Mark ground as SECURED"


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    """Admin panel for Vacancy model"""
    list_display = [
        'vacancy_id', 'get_match_info', 'looking_for_role',
        'count_needed', 'filled_count', 'cost_per_head', 'status', 'created_at'
    ]

    list_filter = [
        'looking_for_role', 'status', 'created_at'
    ]

    search_fields = [
        'vacancy_id', 'match__venue__name',
        'match__host_team__captain__full_name'
    ]

    readonly_fields = ['vacancy_id', 'created_at', 'updated_at', 'slots_remaining']

    ordering = ['-created_at']

    fieldsets = (
        ('Vacancy Details', {
            'fields': ('vacancy_id', 'match', 'looking_for_role')
        }),
        ('Slots & Pricing', {
            'fields': ('count_needed', 'filled_count', 'slots_remaining', 'cost_per_head')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    actions = ['mark_as_filled', 'mark_as_open']

    def get_match_info(self, obj):
        """Display match info"""
        return f"{obj.match.venue.name} - {obj.match.start_time.strftime('%Y-%m-%d %H:%M')}"

    get_match_info.short_description = 'Match Info'

    def slots_remaining(self, obj):
        """Calculate remaining slots"""
        return max(0, obj.count_needed - obj.filled_count)

    slots_remaining.short_description = 'Slots Remaining'

    def mark_as_filled(self, request, queryset):
        """Mark selected vacancies as filled"""
        updated = queryset.update(status='FILLED')
        self.message_user(request, f'{updated} vacancy(ies) marked as filled.')

    mark_as_filled.short_description = "Mark as FILLED"

    def mark_as_open(self, request, queryset):
        """Mark selected vacancies as open"""
        updated = queryset.update(status='OPEN')
        self.message_user(request, f'{updated} vacancy(ies) marked as open.')

    mark_as_open.short_description = "Mark as OPEN"


@admin.register(GroundCheckin)
class GroundCheckinAdmin(admin.ModelAdmin):
    """Admin panel for Ground Check-in model"""
    list_display = [
        'checkin_id', 'get_user_name', 'get_match_info',
        'checkin_time', 'is_successful', 'distance_from_venue'
    ]

    list_filter = [
        'is_successful', 'checkin_time'
    ]

    search_fields = [
        'user__full_name', 'user__phone_number',
        'match__venue__name'
    ]

    readonly_fields = [
        'checkin_id', 'checkin_time', 'created_at', 'updated_at'
    ]

    ordering = ['-checkin_time']

    date_hierarchy = 'checkin_time'

    fieldsets = (
        ('Check-in Details', {
            'fields': ('checkin_id', 'match', 'user', 'checkin_time')
        }),
        ('Location Data', {
            'fields': ('user_lat', 'user_long', 'distance_from_venue')
        }),
        ('Status', {
            'fields': ('is_successful',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def get_user_name(self, obj):
        """Display user name"""
        return obj.user.full_name

    get_user_name.short_description = 'User'
    get_user_name.admin_order_field = 'user__full_name'

    def get_match_info(self, obj):
        """Display match info"""
        return f"{obj.match.venue.name} - {obj.match.start_time.strftime('%Y-%m-%d')}"

    get_match_info.short_description = 'Match'


@admin.register(EscrowTransaction)
class EscrowTransactionAdmin(admin.ModelAdmin):
    """Admin panel for Escrow Transaction model"""
    list_display = [
        'escrow_id', 'get_payer_name', 'get_match_info',
        'amount', 'status', 'created_at'
    ]

    list_filter = [
        'status', 'created_at'
    ]

    search_fields = [
        'escrow_id', 'payer__full_name', 'payer__phone_number',
        'match__venue__name'
    ]

    readonly_fields = [
        'escrow_id', 'created_at', 'updated_at',
        'released_at', 'refunded_at'
    ]

    ordering = ['-created_at']

    date_hierarchy = 'created_at'

    fieldsets = (
        ('Transaction Details', {
            'fields': ('escrow_id', 'match', 'payer', 'amount')
        }),
        ('Status & Conditions', {
            'fields': ('status', 'release_condition')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'released_at', 'refunded_at')
        }),
    )

    actions = ['release_payments', 'refund_payments']

    def get_payer_name(self, obj):
        """Display payer name"""
        return obj.payer.full_name

    get_payer_name.short_description = 'Payer'
    get_payer_name.admin_order_field = 'payer__full_name'

    def get_match_info(self, obj):
        """Display match info"""
        return f"{obj.match.venue.name} - {obj.match.start_time.strftime('%Y-%m-%d')}"

    get_match_info.short_description = 'Match'

    def release_payments(self, request, queryset):
        """Release selected escrow payments"""
        held_transactions = queryset.filter(status='HELD')
        count = 0
        for transaction in held_transactions:
            transaction.release_payment()
            count += 1
        self.message_user(request, f'{count} payment(s) released.')

    release_payments.short_description = "Release selected payments"

    def refund_payments(self, request, queryset):
        """Refund selected escrow payments"""
        held_transactions = queryset.filter(status='HELD')
        count = 0
        for transaction in held_transactions:
            transaction.refund_payment()
            count += 1
        self.message_user(request, f'{count} payment(s) refunded.')

    refund_payments.short_description = "Refund selected payments"