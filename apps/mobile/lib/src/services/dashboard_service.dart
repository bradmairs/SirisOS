import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/dashboard_summary.dart';
import 'auth_service.dart';

class DashboardService {
  DashboardService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<DashboardSummary> fetchDashboard() async {
    final dashboardFuture = _fetchDashboardSummary();
    final recommendationsFuture = _fetchRecommendations();

    final dashboard = await dashboardFuture;
    final recommendations = await recommendationsFuture;
    if (recommendations.isEmpty) return dashboard;

    return dashboard.copyWith(
      briefingItems: <String>[
        ...recommendations,
        ...dashboard.briefingItems,
      ],
    );
  }

  Future<DashboardSummary> _fetchDashboardSummary() async {
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

  Future<List<String>> _fetchRecommendations() async {
    try {
      final uri = Uri.parse(
        '${ApiConfig.baseUrl}/api/v1/intelligence/recommendations',
      );
      final response = await _client
          .get(uri, headers: AuthService.authorizationHeaders)
          .timeout(const Duration(seconds: 8));
      if (response.statusCode != 200) return const [];

      final decoded = jsonDecode(response.body);
      if (decoded is! List) return const [];

      return decoded
          .whereType<Map<String, dynamic>>()
          .take(3)
          .map((item) {
            final title = item['title'] as String? ?? 'Recommendation';
            final message = item['message'] as String? ?? '';
            return message.isEmpty ? title : '$title — $message';
          })
          .toList(growable: false);
    } catch (_) {
      return const [];
    }
  }
}

class DashboardServiceException implements Exception {
  const DashboardServiceException(this.message);

  final String message;

  @override
  String toString() => message;
}
