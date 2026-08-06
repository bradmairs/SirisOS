import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/docker_summary.dart';
import 'auth_service.dart';

class HomelabService {
  HomelabService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<DockerSummary> fetchDockerSummary() async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/homelab/docker');
    final response = await _client
        .get(uri, headers: AuthService.authorizationHeaders)
        .timeout(const Duration(seconds: 8));

    if (response.statusCode == 401) {
      throw const HomelabServiceException('Your session has expired.');
    }
    if (response.statusCode != 200) {
      throw HomelabServiceException(
        'Docker request failed with status ${response.statusCode}.',
      );
    }

    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const HomelabServiceException(
        'Docker response was not a JSON object.',
      );
    }

    return DockerSummary.fromJson(decoded);
  }
}

class HomelabServiceException implements Exception {
  const HomelabServiceException(this.message);

  final String message;

  @override
  String toString() => message;
}
