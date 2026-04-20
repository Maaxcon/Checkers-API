from django.contrib import admin
from .models import Game, MoveEntry


class MoveEntryInline(admin.TabularInline):
    model = MoveEntry
    extra = 0  
    can_delete = False 
    exclude = ('board_before', 'captured_pos') 
    readonly_fields = ('from_pos', 'to_pos', 'is_jump', 'is_promoted', 'time_spent', 'created_at')
    ordering = ('created_at',) 


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'current_turn', 'winner', 'last_move_at', 'created_at')
    
    list_filter = ('status', 'winner', 'current_turn')
    
    search_fields = ('id',)
    
    inlines = [MoveEntryInline]
    
    readonly_fields = ('id', 'created_at', 'updated_at', 'last_move_at')

    fieldsets = (
        ('Game Info', {
            'fields': ('id', 'status', 'winner', 'current_turn')
        }),
        ('Timers', {
            'fields': ('light_time_remaining', 'dark_time_remaining')
        }),
        ('State', {
            'fields': ('board',),
            'classes': ('collapse',) 
        }),
        ('Timestamps', {
            'fields': ('last_move_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MoveEntry)
class MoveEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'game', 'formatted_move', 'is_jump', 'is_promoted', 'time_spent', 'created_at')
    list_filter = ('is_jump', 'is_promoted', 'created_at')
    search_fields = ('game__id',) 
    readonly_fields = ('game', 'from_pos', 'to_pos', 'is_jump', 'captured_pos', 'is_promoted', 'board_before', 'time_spent', 'created_at')

    @admin.display(description='Move (From -> To)')
    def formatted_move(self, obj):
        return f"{obj.from_pos} -> {obj.to_pos}"