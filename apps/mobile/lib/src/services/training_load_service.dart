import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/training_load.dart';
import 'auth_service.dart';

class TrainingLoadService {
  Future<WeeklyTrainingLoad> fetchWeeklyLoad() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}/api/v1/training/weekly-load'),
      headers: AuthService.authorizationHeaders,
    );
    if (response.statusCode != 200) {
      throw Exception('Could not load weekly training load.');
    }
    return WeeklyTrainingLoad.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>);
  }
}
