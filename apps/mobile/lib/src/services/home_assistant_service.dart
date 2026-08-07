import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../core/siris_event_bus.dart';
import '../models/home_assistant_snapshot.dart';
import 'auth_service.dart';

class HomeAssistantService {
  HomeAssistantService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<HomeAssistantSnapshot> fetchSnapshot() async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/homelab/home-assistant/states'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 8));
    if (response.statusCode == 401) {
      throw const HomeAssistantServiceException('Your session has expired.');
    }
    if (response.statusCode != 200) {
      throw HomeAssistantServiceException(
        'Home Assistant request failed with status ${response.statusCode}.',
      );
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const HomeAssistantServiceException('Invalid Home Assistant response.');
    }
    return HomeAssistantSnapshot.fromJson(decoded);
  }

  Future<void> callService({
    required String domain,
    required String service,
    required String entityId,
  }) async {
    final response = await _client
        .post(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/homelab/home-assistant/action'),
          headers: {
            ...AuthService.authorizationHeaders,
            'Content-Type': 'application/json',
          },
          body: jsonEncode({
            'domain': domain,
            'service': service,
            'entity_id': entityId,
          }),
        )
        .timeout(const Duration(seconds: 10));
    if (response.statusCode != 200) {
      throw HomeAssistantServiceException(
        'Home Assistant action failed with status ${response.statusCode}.',
      );
    }
    SirisEventBus.instance.publish(
      ModuleDataChanged(moduleId: 'homelab', reason: 'home_assistant_action'),
    );
  }
}

class HomeAssistantServiceException implements Exception {
  const HomeAssistantServiceException(this.message);
  final String message;

  @override
  String toString() => message;
}
