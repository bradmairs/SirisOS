class TrainingLevelDimension {
  const TrainingLevelDimension({
    required this.dimension,
    required this.score,
    required this.detail,
  });

  factory TrainingLevelDimension.fromJson(Map<String, dynamic> json) =>
      TrainingLevelDimension(
        dimension: json['dimension'] as String,
        score: (json['score'] as num?)?.toDouble(),
        detail: json['detail'] as String,
      );

  final String dimension;
  final double? score;
  final String detail;
}

class TrainingLevel {
  const TrainingLevel({required this.overallScore, required this.dimensions});

  factory TrainingLevel.fromJson(Map<String, dynamic> json) => TrainingLevel(
        overallScore: (json['overall_score'] as num?)?.toDouble(),
        dimensions: (json['dimensions'] as List<dynamic>)
            .whereType<Map<String, dynamic>>()
            .map(TrainingLevelDimension.fromJson)
            .toList(growable: false),
      );

  final double? overallScore;
  final List<TrainingLevelDimension> dimensions;
}
