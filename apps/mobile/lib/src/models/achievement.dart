class Achievement {
  const Achievement({
    required this.id,
    required this.title,
    required this.description,
    required this.unlocked,
    required this.achievedDate,
    required this.progressLabel,
  });

  factory Achievement.fromJson(Map<String, dynamic> json) => Achievement(
        id: json['id'] as String,
        title: json['title'] as String,
        description: json['description'] as String,
        unlocked: json['unlocked'] as bool,
        achievedDate: json['achieved_date'] == null
            ? null
            : DateTime.parse(json['achieved_date'] as String),
        progressLabel: json['progress_label'] as String,
      );

  final String id;
  final String title;
  final String description;
  final bool unlocked;
  final DateTime? achievedDate;
  final String progressLabel;
}
