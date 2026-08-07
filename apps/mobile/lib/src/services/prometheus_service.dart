import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/prometheus_snapshot.dart';
import 'auth_service.dart';

class PrometheusService {
  PrometheusService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<PrometheusSnapshot> fetchSnapshot() async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/homelab/prometheus'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 6));
    if (response.statusCode == 401) {
      throw const PrometheusServiceException('Your session has expired.');
    }
    if (response.statusCode != 200) {
      throw PrometheusServiceException(
        'Prometheus request failed with status ${response.statusCode}.',
      );
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const PrometheusServiceException('Invalid Prometheus response.');
    }
    return PrometheusSnapshot.fromJson(decoded);
  }

  Future<List<Map<String, dynamic>>> query(String expression) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/homelab/prometheus/query')
        .replace(queryParameters: {'query': expression});
    final response = await _client
        .get(uri, headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 6));
    if (response.statusCode != 200) {
      throw PrometheusServiceException(
        'Prometheus query failed with status ${response.statusCode}.',
      );
    }
    final decoded = jsonDecode(response.body);
    final raw = decoded is Map<String, dynamic> ? decoded['result'] : null;
    return raw is List
        ? raw.whereType<Map<String, dynamic>>().toList(growable: false)
        : const [];
  }
}

class PrometheusServiceException implements Exception {
  const PrometheusServiceException(this.message);
  final String message;

  @override
  String toString() => message;
}
