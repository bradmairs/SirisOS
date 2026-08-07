import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/grafana_snapshot.dart';
import 'auth_service.dart';

class GrafanaService {
  GrafanaService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<GrafanaSnapshot> fetchSnapshot() async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/homelab/grafana'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 8));
    if (response.statusCode == 401) {
      throw const GrafanaServiceException('Your session has expired.');
    }
    if (response.statusCode != 200) {
      throw GrafanaServiceException(
        'Grafana request failed with status ${response.statusCode}.',
      );
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const GrafanaServiceException('Invalid Grafana response.');
    }
    return GrafanaSnapshot.fromJson(decoded);
  }
}

class GrafanaServiceException implements Exception {
  const GrafanaServiceException(this.message);
  final String message;

  @override
  String toString() => message;
}
