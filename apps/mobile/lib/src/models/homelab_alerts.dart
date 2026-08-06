class HomelabAlert {
  const HomelabAlert({required this.id, required this.severity, required this.source, required this.title, required this.message});

  factory HomelabAlert.fromJson(Map<String, dynamic> json) => HomelabAlert(
        id: json['id'] as String? ?? '',
        severity: json['severity'] as String? ?? 'warning',
        source: json['source'] as String? ?? 'Homelab',
        title: json['title'] as String? ?? 'Alert',
        message: json['message'] as String? ?? '',
      );

  final String id;
  final String severity;
  final String source;
  final String title;
  final String message;

  bool get isCritical => severity == 'critical';
}

class HomelabAlertSummary {
  const HomelabAlertSummary({required this.status, required this.warningCount, required this.criticalCount, required this.alerts});

  factory HomelabAlertSummary.fromJson(Map<String, dynamic> json) {
    final raw = json['alerts'];
    return HomelabAlertSummary(
      status: json['status'] as String? ?? 'healthy',
      warningCount: json['warning_count'] as int? ?? 0,
      criticalCount: json['critical_count'] as int? ?? 0,
      alerts: raw is List
          ? raw.whereType<Map<String, dynamic>>().map(HomelabAlert.fromJson).toList(growable: false)
          : const [],
    );
  }

  final String status;
  final int warningCount;
  final int criticalCount;
  final List<HomelabAlert> alerts;
}
