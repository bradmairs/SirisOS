import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/health_ingest_status.dart';
import '../models/health_metric_summary.dart';
import '../models/health_snapshot.dart';
import 'auth_service.dart';

class HealthService {
  HealthService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<HealthIngestStatus> fetchIngestStatus() async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/health/status'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 8));

    if (response.statusCode != 200) {
      throw HealthServiceException(
        'Health status request failed with status ${response.statusCode}.',
      );
    }

    return HealthIngestStatus.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<List<HealthMetricSummary>> fetchSummary() async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/health/summary'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 8));

    if (response.statusCode != 200) {
      throw HealthServiceException(
        'Health summary request failed with status ${response.statusCode}.',
      );
    }

    final decoded = jsonDecode(response.body);
    if (decoded is! List) return const [];
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(HealthMetricSummary.fromJson)
        .toList(growable: false);
  }

  Future<List<DailyMetricPoint>> fetchMetricHistory(String metricType,
      {int days = 30}) async {
    final response = await _client
        .get(
          Uri.parse(
              '${ApiConfig.baseUrl}/api/v1/health/metrics/${Uri.encodeComponent(metricType)}/history?days=$days'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 8));

    if (response.statusCode != 200) {
      throw HealthServiceException(
        'Health metric history request failed with status ${response.statusCode}.',
      );
    }

    final decoded = jsonDecode(response.body);
    if (decoded is! List) return const [];
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(DailyMetricPoint.fromJson)
        .toList(growable: false);
  }

  Future<List<UnloggedHealthWorkout>> fetchUnloggedWorkouts({int days = 30}) async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/health/unlogged-workouts?days=$days'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 8));

    if (response.statusCode != 200) {
      throw HealthServiceException(
        'Unlogged workouts request failed with status ${response.statusCode}.',
      );
    }

    final decoded = jsonDecode(response.body);
    if (decoded is! List) return const [];
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(UnloggedHealthWorkout.fromJson)
        .toList(growable: false);
  }

  Future<DailyReadinessPoint?> fetchReadinessToday() async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/health/readiness'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 8));

    if (response.statusCode != 200) {
      throw HealthServiceException(
        'Readiness request failed with status ${response.statusCode}.',
      );
    }

    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) return null;
    return DailyReadinessPoint.fromJson(decoded);
  }

  Future<List<DailyReadinessPoint>> fetchReadinessHistory({int days = 30}) async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/health/readiness/history?days=$days'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 8));

    if (response.statusCode != 200) {
      throw HealthServiceException(
        'Readiness history request failed with status ${response.statusCode}.',
      );
    }

    final decoded = jsonDecode(response.body);
    if (decoded is! List) return const [];
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(DailyReadinessPoint.fromJson)
        .toList(growable: false);
  }

  Future<HealthSnapshot> fetchSnapshot() async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/health/snapshot'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 8));

    if (response.statusCode == 401) {
      throw const HealthServiceException('Your SirisOS session has expired.');
    }
    if (response.statusCode != 200) {
      throw HealthServiceException(
        'Health request failed with status ${response.statusCode}.',
      );
    }

    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const HealthServiceException('Health response was not a JSON object.');
    }

    // Reading a snapshot must be side-effect free. Publishing ModuleDataChanged
    // here caused DashboardService -> HealthService -> Event Bus -> DashboardService
    // refresh loops. Producers should publish only when health data actually changes.
    return HealthSnapshot.fromJson(decoded);
  }
}

class HealthServiceException implements Exception {
  const HealthServiceException(this.message);

  final String message;

  @override
  String toString() => message;
}
