enum MuscleReadinessLevel { ready, recovering, fatigued, noData }

/// Pure translation of a [MuscleGroupFatigue]-shaped fatigue fraction into
/// the labels/estimates the Muscle map UI shows. Kept separate from the
/// widget so the thresholds are unit-testable without a Flutter test
/// harness pulling in HTTP/rendering.
abstract final class MuscleReadiness {
  static MuscleReadinessLevel level({
    required int? daysSinceTrained,
    required double fatigueFraction,
  }) {
    if (daysSinceTrained == null) return MuscleReadinessLevel.noData;
    if (fatigueFraction <= 0.05) return MuscleReadinessLevel.ready;
    if (fatigueFraction < 0.6) return MuscleReadinessLevel.recovering;
    return MuscleReadinessLevel.fatigued;
  }

  static String label(MuscleReadinessLevel level) => switch (level) {
        MuscleReadinessLevel.ready => 'Ready',
        MuscleReadinessLevel.recovering => 'Recovering',
        MuscleReadinessLevel.fatigued => 'Fatigued',
        MuscleReadinessLevel.noData => 'No data yet',
      };

  /// Whole days from [now] until [readyAt]; null once already ready (or with
  /// no estimate at all), so the UI can skip the "ready in" caption.
  static int? daysUntilReady({
    required DateTime? readyAt,
    required double fatigueFraction,
    required DateTime now,
  }) {
    if (readyAt == null || fatigueFraction <= 0.05) return null;
    final days = readyAt.difference(now).inDays;
    return days > 0 ? days : 0;
  }
}
