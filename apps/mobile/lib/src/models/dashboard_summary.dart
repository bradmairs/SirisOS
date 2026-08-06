class DashboardCardData {
  const DashboardCardData({
    required this.title,
    required this.value,
    required this.subtitle,
    required this.status,
  });

  factory DashboardCardData.fromJson(Map<String, dynamic> json) {
    return DashboardCardData(
      title: json['title'] as String? ?? 'Unknown',
      value: json['value'] as String? ?? '—',
      subtitle: json['subtitle'] as String? ?? '',
      status: json['status'] as String? ?? 'unknown',
    );
  }

  final String title;
  final String value;
  final String subtitle;
  final String status;
}

class DashboardSummary {
  const DashboardSummary({
    required this.greetingName,
    required this.homelab,
    required this.running,
    required this.gym,
    required this.system,
    required this.briefingItems,
    required this.generatedAt,
  });

  factory DashboardSummary.fromJson(Map<String, dynamic> json) {
    final briefing = json['briefing_items'];
    return DashboardSummary(
      greetingName: json['greeting_name'] as String? ?? 'Brad',
      homelab: DashboardCardData.fromJson(
        json['homelab'] as Map<String, dynamic>,
      ),
      running: DashboardCardData.fromJson(
        json['running'] as Map<String, dynamic>,
      ),
      gym: DashboardCardData.fromJson(
        json['gym'] as Map<String, dynamic>,
      ),
      system: DashboardCardData.fromJson(
        json['system'] as Map<String, dynamic>,
      ),
      briefingItems: briefing is List
          ? briefing.whereType<String>().toList(growable: false)
          : const [],
      generatedAt: DateTime.tryParse(json['generated_at'] as String? ?? '') ??
          DateTime.now(),
    );
  }

  final String greetingName;
  final DashboardCardData homelab;
  final DashboardCardData running;
  final DashboardCardData gym;
  final DashboardCardData system;
  final List<String> briefingItems;
  final DateTime generatedAt;

  DashboardSummary copyWith({
    List<String>? briefingItems,
    DateTime? generatedAt,
  }) {
    return DashboardSummary(
      greetingName: greetingName,
      homelab: homelab,
      running: running,
      gym: gym,
      system: system,
      briefingItems: briefingItems ?? this.briefingItems,
      generatedAt: generatedAt ?? this.generatedAt,
    );
  }
}
