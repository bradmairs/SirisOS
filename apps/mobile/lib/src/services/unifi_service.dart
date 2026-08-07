import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/unifi_snapshot.dart';
import 'auth_service.dart';

class UniFiService {
  UniFiService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<UniFiSnapshot> fetchSnapshot({bool refresh = false}) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/homelab/unifi').replace(
      queryParameters: refresh ? const {'refresh': 'true'} : null,
    );
    final response = await _client
        .get(uri, headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 8));
    if (response.statusCode == 401) {
      throw const UniFiServiceException('Your session has expired.');
    }
    if (response.statusCode != 200) {
      throw UniFiServiceException(
        'UniFi request failed with status ${response.statusCode}.',
      );
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const UniFiServiceException('Invalid UniFi response.');
    }
    return UniFiSnapshot.fromJson(decoded);
  }
}

class UniFiServiceException implements Exception {
  const UniFiServiceException(this.message);
  final String message;

  @override
  String toString() => message;
}
