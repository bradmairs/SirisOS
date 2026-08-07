class TimeSeriesObservation {
  const TimeSeriesObservation({
    required this.observedAt,
    required this.source,
    required this.metric,
    required this.dimensions,
    this.numericValue,
    this.textValue,
  });

  final DateTime observedAt;
  final String source;
  final String metric;
  final Map<String, String> dimensions;
  final double? numericValue;
  final String? textValue;

  factory TimeSeriesObservation.fromJson(Map<String, dynamic> json) {
    final rawDimensions = json['dimensions'];
    final dimensions = <String, String>{};
    if (rawDimensions is Map) {
      for (final entry in rawDimensions.entries) {
        dimensions[entry.key.toString()] = entry.value.toString();
      }
    }
    return TimeSeriesObservation(
      observedAt: DateTime.parse(json['observed_at'] as String),
      source: json['source'] as String? ?? '',
      metric: json['metric'] as String? ?? '',
      dimensions: dimensions,
      numericValue: (json['numeric_value'] as num?)?.toDouble(),
      textValue: json['text_value'] as String?,
    );
  }
}
