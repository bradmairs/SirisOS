import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/health_snapshot.dart';
import 'auth_service.dart';

class HealthService {
  HealthService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<HealthSnapshot> fetchSnapshot() async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/health/snapshot'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 15));

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
    return HealthSnapshot.fromJson(decoded);
  }
}

class HealthServiceException implements Exception {
  const HealthServiceException(this.message);

  final String message;

  @override
  String toString() => message;
}
