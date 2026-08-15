class HealthIngestStatus {
  const HealthIngestStatus({
    required this.configured,
    required this.lastSync,
    required this.recordsReceived,
    required this.lastError,
  });

  factory HealthIngestStatus.fromJson(Map<String, dynamic> json) =>
      HealthIngestStatus(
        configured: json['configured'] as bool,
        lastSync: json['last_sync'] == null
            ? null
            : DateTime.parse(json['last_sync'] as String),
        recordsReceived: json['records_received'] as int,
        lastError: json['last_error'] as String?,
      );

  final bool configured;
  final DateTime? lastSync;
  final int recordsReceived;
  final String? lastError;
}
