import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../core/siris_event_bus.dart';
import '../models/exercise_progress.dart';
import '../models/gym_workout.dart';
import '../models/workout_template.dart';
import 'auth_service.dart';

class GymService {
  Future<List<GymWorkout>> fetchWorkouts() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/gym/workouts'),
      headers: AuthService.authorizationHeaders,
    );
    if (response.statusCode != 200) throw Exception('Could not load workouts.');
    final decoded = jsonDecode(response.body);
    if (decoded is! List) return const [];
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(GymWorkout.fromJson)
        .toList();
  }

  Future<List<ExerciseProgress>> fetchExercises() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/gym/exercises'),
      headers: AuthService.authorizationHeaders,
    );
    if (response.statusCode != 200)
      throw Exception('Could not load exercise progress.');
    final decoded = jsonDecode(response.body);
    if (decoded is! List) return const [];
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(ExerciseProgress.fromJson)
        .toList(growable: false);
  }

  Future<ProgressiveOverloadSuggestion> fetchSuggestion(String exercise) async {
    final response = await http.get(
      Uri.parse(
          '${ApiConfig.baseUrl}/api/v1/gym/exercises/${Uri.encodeComponent(exercise)}/suggestion'),
      headers: AuthService.authorizationHeaders,
    );
    if (response.statusCode != 200)
      throw Exception('Could not load a suggestion for $exercise.');
    return ProgressiveOverloadSuggestion.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<DeloadSuggestion> fetchDeloadSuggestion(String exercise) async {
    final response = await http.get(
      Uri.parse(
          '${ApiConfig.baseUrl}/api/v1/gym/exercises/${Uri.encodeComponent(exercise)}/deload'),
      headers: AuthService.authorizationHeaders,
    );
    if (response.statusCode != 200)
      throw Exception('Could not load a deload check for $exercise.');
    return DeloadSuggestion.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<List<String>> fetchMuscleGroups() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/gym/muscle-groups'),
      headers: AuthService.authorizationHeaders,
    );
    if (response.statusCode != 200)
      throw Exception('Could not load muscle groups.');
    final decoded = jsonDecode(response.body);
    if (decoded is! List) return const [];
    return decoded.whereType<String>().toList(growable: false);
  }

  Future<List<String>> fetchUntaggedExercises() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/gym/muscle-groups/untagged'),
      headers: AuthService.authorizationHeaders,
    );
    if (response.statusCode != 200)
      throw Exception('Could not load untagged exercises.');
    final decoded = jsonDecode(response.body);
    if (decoded is! List) return const [];
    return decoded.whereType<String>().toList(growable: false);
  }

  Future<List<MuscleGroupWorkload>> fetchMuscleGroupWorkload({int days = 7}) async {
    final response = await http.get(
      Uri.parse(
          '${ApiConfig.baseUrl}/api/v1/gym/muscle-groups/workload?days=$days'),
      headers: AuthService.authorizationHeaders,
    );
    if (response.statusCode != 200)
      throw Exception('Could not load muscle group workload.');
    final decoded = jsonDecode(response.body);
    if (decoded is! List) return const [];
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(MuscleGroupWorkload.fromJson)
        .toList(growable: false);
  }

  Future<void> tagExercise(String exercise, String muscleGroup) async {
    final response = await http.put(
      Uri.parse(
          '${ApiConfig.baseUrl}/api/v1/gym/exercises/${Uri.encodeComponent(exercise)}/muscle-group'),
      headers: {
        ...AuthService.authorizationHeaders,
        'Content-Type': 'application/json',
      },
      body: jsonEncode({'muscle_group': muscleGroup}),
    );
    if (response.statusCode != 204) {
      throw Exception('Could not tag $exercise.');
    }
  }

  Future<List<WorkoutTemplate>> fetchTemplates() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/gym/templates'),
      headers: AuthService.authorizationHeaders,
    );
    if (response.statusCode != 200)
      throw Exception('Could not load workout templates.');
    final decoded = jsonDecode(response.body);
    if (decoded is! List) return const [];
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(WorkoutTemplate.fromJson)
        .toList(growable: false);
  }

  Future<WorkoutTemplate> createTemplate({
    required String name,
    required List<WorkoutTemplateExercise> exercises,
  }) async {
    final response = await http.post(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/gym/templates'),
      headers: {
        ...AuthService.authorizationHeaders,
        'Content-Type': 'application/json'
      },
      body: jsonEncode({
        'name': name,
        'exercises': exercises.map((item) => item.toJson()).toList(),
      }),
    );
    final decoded = jsonDecode(response.body.isEmpty ? '{}' : response.body);
    if (response.statusCode != 201) {
      throw Exception(decoded is Map<String, dynamic>
          ? decoded['detail'] ?? 'Could not save template.'
          : 'Could not save template.');
    }
    SirisEventBus.instance.publish(
      ModuleDataChanged(moduleId: 'gym', reason: 'template_created'),
    );
    return WorkoutTemplate.fromJson(decoded as Map<String, dynamic>);
  }

  Future<void> deleteTemplate(int templateId) async {
    final response = await http.delete(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/gym/templates/$templateId'),
      headers: AuthService.authorizationHeaders,
    );
    if (response.statusCode != 204)
      throw Exception('Could not delete template.');
    SirisEventBus.instance.publish(
      ModuleDataChanged(moduleId: 'gym', reason: 'template_deleted'),
    );
  }

  Future<GymWorkout> createWorkout(
      {required DateTime date,
      required String name,
      String? notes,
      required List<GymSet> sets}) async {
    final response = await http.post(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/gym/workouts'),
      headers: {
        ...AuthService.authorizationHeaders,
        'Content-Type': 'application/json'
      },
      body: jsonEncode({
        'workout_date': date.toIso8601String().split('T').first,
        'name': name,
        'notes': notes,
        'sets': sets
            .map((item) => {
                  'exercise': item.exercise,
                  'weight_kg': item.weightKg,
                  'reps': item.reps,
                  'rir': item.rir,
                })
            .toList(),
      }),
    );
    if (response.statusCode != 201) {
      final decoded = jsonDecode(response.body);
      throw Exception(decoded is Map<String, dynamic>
          ? decoded['detail'] ?? 'Could not save workout.'
          : 'Could not save workout.');
    }
    SirisEventBus.instance.publish(
      ModuleDataChanged(moduleId: 'gym', reason: 'workout_logged'),
    );
    SirisEventBus.instance.publish(
      NotificationStateChanged(source: 'gym'),
    );
    return GymWorkout.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>);
  }
}
