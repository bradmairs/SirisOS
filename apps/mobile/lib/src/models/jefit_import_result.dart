class JefitImportResult {
  const JefitImportResult({
    required this.sessionsImported,
    required this.sessionsSkipped,
    required this.setsImported,
    required this.earliestDate,
    required this.latestDate,
    required this.errors,
  });

  final int sessionsImported;
  final int sessionsSkipped;
  final int setsImported;
  final DateTime? earliestDate;
  final DateTime? latestDate;
  final List<String> errors;

  factory JefitImportResult.fromJson(Map<String, dynamic> json) => JefitImportResult(
        sessionsImported: json['sessions_imported'] as int,
        sessionsSkipped: json['sessions_skipped'] as int,
        setsImported: json['sets_imported'] as int,
        earliestDate: json['earliest_date'] == null ? null : DateTime.parse(json['earliest_date'] as String),
        latestDate: json['latest_date'] == null ? null : DateTime.parse(json['latest_date'] as String),
        errors: (json['errors'] as List<dynamic>? ?? const []).whereType<String>().toList(growable: false),
      );
}
