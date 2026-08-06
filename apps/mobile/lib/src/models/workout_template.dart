class WorkoutTemplate {
  const WorkoutTemplate({
    required this.id,
    required this.name,
    required this.createdAt,
    required this.exercises,
  });

  factory WorkoutTemplate.fromJson(Map<String, dynamic> json) => WorkoutTemplate(
        id: json['id'] as int,
        name: json['name'] as String,
        createdAt: DateTime.parse(json['created_at'] as String),
        exercises: (json['exercises'] as List<dynamic>? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(WorkoutTemplateExercise.fromJson)
            .toList(growable: false),
      );

  final int id;
  final String name;
  final DateTime createdAt;
  final List<WorkoutTemplateExercise> exercises;
}

class WorkoutTemplateExercise {
  const WorkoutTemplateExercise({
    required this.exercise,
    required this.targetSets,
    required this.targetReps,
    required this.targetRir,
  });

  factory WorkoutTemplateExercise.fromJson(Map<String, dynamic> json) =>
      WorkoutTemplateExercise(
        exercise: json['exercise'] as String,
        targetSets: json['target_sets'] as int? ?? 1,
        targetReps: json['target_reps'] as int? ?? 8,
        targetRir: json['target_rir'] as int?,
      );

  final String exercise;
  final int targetSets;
  final int targetReps;
  final int? targetRir;

  Map<String, dynamic> toJson() => {
        'exercise': exercise,
        'target_sets': targetSets,
        'target_reps': targetReps,
        'target_rir': targetRir,
      };
}
