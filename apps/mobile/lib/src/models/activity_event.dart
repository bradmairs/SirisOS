class ActivityEvent {
  const ActivityEvent({
    required this.id,
    required this.occurredAt,
    required this.module,
    required this.eventType,
    required this.title,
    required this.message,
    required this.severity,
    required this.user,
    required this.isUnread,
  });

  factory ActivityEvent.fromJson(Map<String, dynamic> json) => ActivityEvent(
        id: json['id'] as int,
        occurredAt: DateTime.parse(json['occurred_at'] as String),
        module: json['module'] as String,
        eventType: json['event_type'] as String,
        title: json['title'] as String,
        message: json['message'] as String,
        severity: json['severity'] as String? ?? 'info',
        user: json['user'] as String?,
        isUnread: json['is_unread'] as bool? ?? false,
      );

  final int id;
  final DateTime occurredAt;
  final String module;
  final String eventType;
  final String title;
  final String message;
  final String severity;
  final String? user;
  final bool isUnread;
}
