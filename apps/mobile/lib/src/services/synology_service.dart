import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/synology_snapshot.dart';
import 'auth_service.dart';

class SynologyService {
  SynologyService({http.Client? client}) : _client = client ?? http.Client();
  final http.Client _client;

  Future<SynologySnapshot> fetchSnapshot() async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/homelab/synology'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 10));
    if (response.statusCode == 401) {
      throw const SynologyServiceException('Your session has expired.');
    }
    if (response.statusCode != 200) {
      throw SynologyServiceException('Synology request failed with status ${response.statusCode}.');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const SynologyServiceException('Invalid Synology response.');
    }
    return SynologySnapshot.fromJson(decoded);
  }
}

class SynologyServiceException implements Exception {
  const SynologyServiceException(this.message);
  final String message;
  @override
  String toString() => message;
}
