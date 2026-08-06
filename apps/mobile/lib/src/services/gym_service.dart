import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/exercise_progress.dart';
import '../models/gym_workout.dart';
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
    return decoded.whereType<Map<String, dynamic>>().map(GymWorkout.fromJson).toList();
  }

  Future<List<ExerciseProgress>> fetchExercises() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/gym/exercises'),
      headers: AuthService.authorizationHeaders,
    );
    if (response.statusCode != 200) throw Exception('Could not load exercise progress.');
    final decoded = jsonDecode(response.body);
    if (decoded is! List) return const [];
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(ExerciseProgress.fromJson)
        .toList(growable: false);
  }

  Future<void> createWorkout({required DateTime date, required String name, String? notes, required List<GymSet> sets}) async {
    final response = await http.post(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/gym/workouts'),
      headers: {...AuthService.authorizationHeaders, 'Content-Type': 'application/json'},
      body: jsonEncode({
        'workout_date': date.toIso8601String().split('T').first,
        'name': name,
        'notes': notes,
        'sets': sets.map((item) => {
          'exercise': item.exercise,
          'weight_kg': item.weightKg,
          'reps': item.reps,
          'rir': item.rir,
        }).toList(),
      }),
    );
    if (response.statusCode != 201) {
      final decoded = jsonDecode(response.body);
      throw Exception(decoded is Map<String, dynamic> ? decoded['detail'] ?? 'Could not save workout.' : 'Could not save workout.');
    }
  }
}
