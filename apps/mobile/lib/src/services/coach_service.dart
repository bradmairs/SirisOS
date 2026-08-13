import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/coach_report.dart';
import 'auth_service.dart';

class CoachService {
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
}
