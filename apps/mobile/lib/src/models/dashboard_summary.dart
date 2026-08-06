class DashboardCardData {
  const DashboardCardData({
    required this.title,
    required this.value,
    required this.subtitle,
    required this.status,
  });

  factory DashboardCardData.fromJson(Map<String, dynamic> json) {
    return DashboardCardData(
      title: json['title'] as String,
      value: json['value'] as String,
      subtitle: json['subtitle'] as String,
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
    required this.recovery,
    required this.gym,
    required this.today,
    required this.briefing,
    required this.generatedAt,
  });

  factory DashboardSummary.fromJson(Map<String, dynamic> json) {
    return DashboardSummary(
      greetingName: json['greeting_name'] as String,
      homelab: DashboardCardData.fromJson(
        json['homelab'] as Map<String, dynamic>,
      ),
      recovery: DashboardCardData.fromJson(
        json['recovery'] as Map<String, dynamic>,
      ),
      gym: DashboardCardData.fromJson(
        json['gym'] as Map<String, dynamic>,
      ),
      today: DashboardCardData.fromJson(
        json['today'] as Map<String, dynamic>,
      ),
      briefing: json['briefing'] as String,
      generatedAt: DateTime.parse(json['generated_at'] as String),
    );
  }

  final String greetingName;
  final DashboardCardData homelab;
  final DashboardCardData recovery;
  final DashboardCardData gym;
  final DashboardCardData today;
  final String briefing;
  final DateTime generatedAt;
}
