import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/docker_summary.dart';
import '../models/host_metrics.dart';
import 'auth_service.dart';

class HomelabService {
  HomelabService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<DockerSummary> fetchDockerSummary() async {
    final decoded = await _getJsonObject('/api/v1/homelab/docker');
    return DockerSummary.fromJson(decoded);
  }

  Future<HostMetrics> fetchHostMetrics() async {
    final decoded = await _getJsonObject('/api/v1/homelab/host');
    return HostMetrics.fromJson(decoded);
  }

  Future<List<HostMetricHistorySample>> fetchHostHistory({int hours = 24}) async {
    final response = await _get('/api/v1/homelab/host/history?hours=$hours');
    final decoded = jsonDecode(response.body);
    if (decoded is! List) {
      throw const HomelabServiceException(
        'Host history response was not a JSON list.',
      );
    }
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(HostMetricHistorySample.fromJson)
        .toList(growable: false);
  }

  Future<Map<String, dynamic>> _getJsonObject(String path) async {
    final response = await _get(path);
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const HomelabServiceException(
        'Homelab response was not a JSON object.',
      );
    }
    return decoded;
  }

  Future<http.Response> _get(String path) async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}$path'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 8));

    if (response.statusCode == 401) {
      throw const HomelabServiceException('Your session has expired.');
    }
    if (response.statusCode != 200) {
      throw HomelabServiceException(
        'Homelab request failed with status ${response.statusCode}.',
      );
    }
    return response;
  }
}

class HomelabServiceException implements Exception {
  const HomelabServiceException(this.message);

  final String message;

  @override
  String toString() => message;
}
