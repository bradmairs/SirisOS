class PrometheusSnapshot {
  const PrometheusSnapshot({
    required this.configured,
    required this.available,
    required this.healthyTargets,
    required this.unhealthyTargets,
    required this.totalTargets,
    this.error,
  });

  final bool configured;
  final bool available;
  final int healthyTargets;
  final int unhealthyTargets;
  final int totalTargets;
  final String? error;

  factory PrometheusSnapshot.fromJson(Map<String, dynamic> json) =>
      PrometheusSnapshot(
        configured: json['configured'] as bool? ?? false,
        available: json['available'] as bool? ?? false,
        healthyTargets: json['healthy_targets'] as int? ?? 0,
        unhealthyTargets: json['unhealthy_targets'] as int? ?? 0,
        totalTargets: json['total_targets'] as int? ?? 0,
        error: json['error'] as String?,
      );
}
