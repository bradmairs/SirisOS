class GymSet {
  const GymSet({required this.exercise, required this.weightKg, required this.reps, required this.rir});

  factory GymSet.fromJson(Map<String, dynamic> json) => GymSet(
        exercise: json['exercise'] as String? ?? 'Exercise',
        weightKg: (json['weight_kg'] as num?)?.toDouble() ?? 0,
        reps: json['reps'] as int? ?? 0,
        rir: json['rir'] as int?,
      );

  final String exercise;
  final double weightKg;
  final int reps;
  final int? rir;
  double get volumeKg => weightKg * reps;
}

class GymWorkout {
  const GymWorkout({required this.id, required this.date, required this.name, required this.notes, required this.totalVolumeKg, required this.sets});

  factory GymWorkout.fromJson(Map<String, dynamic> json) => GymWorkout(
        id: json['id'] as int? ?? 0,
        date: DateTime.tryParse(json['workout_date'] as String? ?? '') ?? DateTime.now(),
        name: json['name'] as String? ?? 'Workout',
        notes: json['notes'] as String?,
        totalVolumeKg: (json['total_volume_kg'] as num?)?.toDouble() ?? 0,
        sets: (json['sets'] as List? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(GymSet.fromJson)
            .toList(growable: false),
      );

  final int id;
  final DateTime date;
  final String name;
  final String? notes;
  final double totalVolumeKg;
  final List<GymSet> sets;
}
