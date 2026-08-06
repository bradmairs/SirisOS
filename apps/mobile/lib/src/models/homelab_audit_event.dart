class HomelabAuditEvent {
  const HomelabAuditEvent({
    required this.id,
    required this.occurredAt,
    required this.username,
    required this.containerId,
    required this.containerName,
    required this.action,
    required this.result,
    required this.detail,
  });

  factory HomelabAuditEvent.fromJson(Map<String, dynamic> json) =>
      HomelabAuditEvent(
        id: json['id'] as int? ?? 0,
        occurredAt:
            DateTime.tryParse(json['occurred_at'] as String? ?? '') ??
                DateTime.now(),
        username: json['username'] as String? ?? 'unknown',
        containerId: json['container_id'] as String? ?? '',
        containerName: json['container_name'] as String?,
        action: json['action'] as String? ?? 'unknown',
        result: json['result'] as String? ?? 'unknown',
        detail: json['detail'] as String?,
      );

  final int id;
  final DateTime occurredAt;
  final String username;
  final String containerId;
  final String? containerName;
  final String action;
  final String result;
  final String? detail;

  String get targetLabel => containerName ?? containerId;
}
