import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import 'auth_service.dart';

class ActionService {
  Future<String> execute(
      String capabilityId, Map<String, String> params) async {
    final response = await http.post(
      Uri.parse(
          '${ApiConfig.baseUrl}/api/v1/actions/${Uri.encodeComponent(capabilityId)}/execute'),
      headers: {
        ...AuthService.authorizationHeaders,
        'Content-Type': 'application/json',
      },
      body: jsonEncode({'params': params, 'confirm': true}),
    );
    final decoded = jsonDecode(response.body.isEmpty ? '{}' : response.body);
    if (response.statusCode != 200) {
      throw ActionServiceException(
        decoded is Map<String, dynamic>
            ? decoded['detail'] as String? ?? 'Action failed.'
            : 'Action failed.',
      );
    }
    return decoded is Map<String, dynamic>
        ? decoded['result'] as String? ?? 'Done.'
        : 'Done.';
  }
}

class ActionServiceException implements Exception {
  const ActionServiceException(this.message);
  final String message;

  @override
  String toString() => message;
}
