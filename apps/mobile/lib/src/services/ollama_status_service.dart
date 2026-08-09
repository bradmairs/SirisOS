import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import 'auth_service.dart';

class OllamaStatus {
  const OllamaStatus({
    required this.configured,
    required this.reachable,
    required this.model,
    required this.modelAvailable,
  });

  final bool configured;
  final bool reachable;
  final String? model;
  final bool modelAvailable;

  factory OllamaStatus.fromJson(Map<String, dynamic> json) => OllamaStatus(
        configured: json['configured'] == true,
        reachable: json['reachable'] == true,
        model: json['model'] as String?,
        modelAvailable: json['model_available'] == true,
      );
}

class OllamaStatusService {
  Future<OllamaStatus> status() async {
    final response = await http
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/intelligence/ollama-status'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 10));
    if (response.statusCode != 200) {
      throw OllamaStatusException('Unable to check Ollama status (${response.statusCode}).');
    }
    return OllamaStatus.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }
}

class OllamaStatusException implements Exception {
  const OllamaStatusException(this.message);
  final String message;

  @override
  String toString() => message;
}
