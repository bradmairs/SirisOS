import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/achievement.dart';
import '../models/ask_siris_answer.dart';
import '../models/coach_report.dart';
import '../models/training_conflict_check.dart';
import '../models/training_level.dart';
import 'auth_service.dart';

class CoachService {
  Future<List<Achievement>> fetchAchievements() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/coach/achievements'),
      headers: AuthService.authorizationHeaders,
    );
    if (response.statusCode != 200) {
      throw Exception('Could not load achievements.');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! List) return const [];
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(Achievement.fromJson)
        .toList(growable: false);
  }

  Future<TrainingConflictCheck> fetchConflictCheck() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/coach/conflict-check'),
      headers: AuthService.authorizationHeaders,
    );
    if (response.statusCode != 200) {
      throw Exception('Could not check for a training conflict.');
    }
    return TrainingConflictCheck.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<WeeklyCoachReport> fetchWeeklyReport() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/coach/weekly-report'),
      headers: AuthService.authorizationHeaders,
    );
    if (response.statusCode != 200) {
      throw Exception('Could not load this week\'s coach report.');
    }
    return WeeklyCoachReport.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<TrainingLevel> fetchTrainingLevel() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/coach/training-level'),
      headers: AuthService.authorizationHeaders,
    );
    if (response.statusCode != 200) {
      throw Exception('Could not load training level.');
    }
    return TrainingLevel.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<AskSirisAnswer> ask(String question) async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/coach/ask')
          .replace(queryParameters: {'question': question}),
      headers: AuthService.authorizationHeaders,
    );
    if (response.statusCode != 200) {
      final decoded = jsonDecode(response.body.isEmpty ? '{}' : response.body);
      throw Exception(decoded is Map<String, dynamic>
          ? decoded['detail'] ?? 'Could not get an answer.'
          : 'Could not get an answer.');
    }
    return AskSirisAnswer.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>);
  }
}
