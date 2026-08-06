import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/dashboard_summary.dart';
import 'auth_service.dart';

class DashboardService {
  DashboardService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<DashboardSummary> fetchDashboard() async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/dashboard');
    final response = await _client
        .get(uri, headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 8));

    if (response.statusCode == 401) {
      throw const DashboardServiceException('Your session has expired.');
    }
    if (response.statusCode != 200) {
      throw DashboardServiceException(
        'Dashboard request failed with status ${response.statusCode}.',
      );
    }

    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const DashboardServiceException(
        'Dashboard response was not a JSON object.',
      );
    }

    return DashboardSummary.fromJson(decoded);
  }
}

class DashboardServiceException implements Exception {
  const DashboardServiceException(this.message);

  final String message;

  @override
  String toString() => message;
}
